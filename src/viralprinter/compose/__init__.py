"""Compose: render a Timeline to an mp4 with one ffmpeg call.

Every beat becomes one trimmed, normalized segment; the segments are concatenated
in filter_complex, so there are no intermediate files and no second encode. What
the timeline cannot express is refused rather than dropped: a shot too short for
its beat, a build without the filter an overlay needs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from viralprinter.timeline import TextOverlay, Timeline

__all__ = ["ComposeError", "render"]

_STDERR_TAIL_LINES = 15
_SAMPLE_RATE = 48000
_EPS = 1e-6
# A source a frame or two short of what a beat asks for is rounding, not a
# missing clip.
_SOURCE_SLACK = 0.05

_AFORMAT = f"aformat=sample_fmts=fltp:sample_rates={_SAMPLE_RATE}:channel_layouts=stereo"

_TEXT_Y = {"top": "h*0.10", "center": "(h-text_h)/2", "bottom": "h-text_h-h*0.12"}

# drawtext needs a face. fontconfig is absent from many ffmpeg builds, so a real
# file is passed when one can be found; VIRALPRINTER_FONT overrides.
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)

_FILTER_LINE = re.compile(r"^\s*[A-Z.]{2,3}\s+(\S+)\s+\S+->\S+")


class ComposeError(RuntimeError):
    """A render could not be planned or ffmpeg refused it."""

    def __init__(self, message: str, stderr_tail: str = "") -> None:
        self.stderr_tail = stderr_tail
        super().__init__(f"{message}\n{stderr_tail}" if stderr_tail else message)


@dataclass(frozen=True, slots=True)
class _Probe:
    duration: float | None
    has_audio: bool


def render(timeline: Timeline, out: str | Path, *, dry_run: bool = False) -> Path | list[str]:
    """Render `timeline` to `out`, returning the written path.

    With dry_run=True nothing is encoded and the planned ffmpeg argv is returned
    instead. A dry run still reads the sources it can find (ffprobe decides
    whether a beat carries audio); sources that are absent are planned silent.
    """
    out_path = Path(out)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None and not dry_run:
        raise ComposeError("ffmpeg not found on PATH")

    probes = _probe_sources(timeline, dry_run=dry_run)
    cmd = _build_command(timeline, out_path, ffmpeg=ffmpeg or "ffmpeg", probes=probes)
    if dry_run:
        return cmd

    _require_filters(ffmpeg or "ffmpeg", timeline)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ComposeError(f"ffmpeg exited {proc.returncode} rendering {out_path}", _tail(proc.stderr))
    if not out_path.exists():
        raise ComposeError(f"ffmpeg reported success but wrote no {out_path}", _tail(proc.stderr))
    return out_path


def _build_command(
    t: Timeline, out: Path, *, ffmpeg: str, probes: dict[Path, _Probe]
) -> list[str]:
    w, h, fps = t.canvas.width, t.canvas.height, t.canvas.fps
    inputs: list[str] = []
    chains: list[str] = []
    segments: list[str] = []
    n_inputs = 0
    cursor = 0.0

    for beat in t.beats:
        # Beat times are absolute, so a hole between beats is black, not a
        # silent shift of everything after it.
        gap = beat.start - cursor
        if gap > _EPS:
            seg = len(segments)
            chains.append(f"color=c=black:s={w}x{h}:r={_num(fps)}:d={_num(gap)},setsar=1,format=yuv420p[v{seg}]")
            chains.append(f"anullsrc=r={_SAMPLE_RATE}:cl=stereo:d={_num(gap)},{_AFORMAT}[a{seg}]")
            segments.append(f"[v{seg}][a{seg}]")

        seg = len(segments)
        src = t.resolve(beat.shot.src)
        idx = n_inputs
        n_inputs += 1
        inputs += ["-ss", _num(beat.shot.in_point), "-t", _num(beat.duration), "-i", str(src)]

        video = (
            f"[{idx}:v]fps={_num(fps)},"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,"
            f"trim=duration={_num(beat.duration)},setpts=PTS-STARTPTS"
        )
        if beat.text:
            video += "," + _drawtext(beat.text, h)
        chains.append(f"{video},format=yuv420p[v{seg}]")

        if probes[src].has_audio:
            # apad then atrim so the segment is exactly as long as the beat even
            # when the source's audio ends before its video.
            chains.append(
                f"[{idx}:a]{_AFORMAT},apad,atrim=duration={_num(beat.duration)},asetpts=PTS-STARTPTS[a{seg}]"
            )
        else:
            chains.append(f"anullsrc=r={_SAMPLE_RATE}:cl=stereo:d={_num(beat.duration)},{_AFORMAT}[a{seg}]")

        segments.append(f"[v{seg}][a{seg}]")
        cursor = beat.end

    chains.append(f"{''.join(segments)}concat=n={len(segments)}:v=1:a=1[vcat][acat]")
    vout, aout = "[vcat]", "[acat]"

    if t.subtitles.mode == "burn":
        if not t.subtitles.src:
            raise ComposeError("subtitles mode 'burn' needs subtitles.src, the path to an .srt file")
        chains.append(f"[vcat]subtitles=filename={_escape(str(t.resolve(t.subtitles.src)))}[vsub]")
        vout = "[vsub]"

    music = t.audio.music if t.audio else None
    if music:
        idx = n_inputs
        n_inputs += 1
        inputs += ["-i", str(t.resolve(music.src))]
        chains.append(f"[{idx}:a]{_AFORMAT},volume={_num(music.gain_db)}dB[mus]")
        # normalize=0: amix otherwise halves the bed to make room for the music.
        chains.append("[acat][mus]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amix]")
        aout = "[amix]"

    return [
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        *inputs,
        "-filter_complex", ";".join(chains),
        "-map", vout, "-map", aout,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-r", _num(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", str(_SAMPLE_RATE), "-ac", "2",
        "-movflags", "+faststart",
        str(out),
    ]


def _probe_sources(t: Timeline, *, dry_run: bool) -> dict[Path, _Probe]:
    ffprobe = shutil.which("ffprobe")
    probes: dict[Path, _Probe] = {}
    for beat in t.beats:
        src = t.resolve(beat.shot.src)
        if src not in probes:
            probes[src] = _probe(ffprobe, src, dry_run=dry_run)

    for beat in t.beats:
        probe = probes[t.resolve(beat.shot.src)]
        needed = beat.shot.in_point + beat.duration
        if probe.duration is not None and needed > probe.duration + _SOURCE_SLACK:
            raise ComposeError(
                f"beat {beat.label!r} needs {needed:.2f}s of {beat.shot.src} "
                f"(in {beat.shot.in_point:.2f} + {beat.duration:.2f}) but it is {probe.duration:.2f}s long"
            )

    if not dry_run:
        music = t.audio.music if t.audio else None
        if music:
            _require_file(t.resolve(music.src), "music")
        if t.subtitles.mode == "burn" and t.subtitles.src:
            _require_file(t.resolve(t.subtitles.src), "subtitles")
    return probes


def _probe(ffprobe: str | None, path: Path, *, dry_run: bool) -> _Probe:
    if not path.exists() or ffprobe is None:
        if dry_run:
            return _Probe(None, False)
        if ffprobe is None:
            raise ComposeError("ffprobe not found on PATH")
        raise ComposeError(f"shot source not found: {path}")

    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise ComposeError(f"ffprobe could not read {path}", _tail(proc.stderr))
    data = json.loads(proc.stdout or "{}")
    raw = (data.get("format") or {}).get("duration")
    try:
        duration = float(raw)
    except (TypeError, ValueError):
        duration = None
    return _Probe(duration, any(s.get("codec_type") == "audio" for s in data.get("streams") or []))


def _require_file(path: Path, what: str) -> None:
    if not path.exists():
        raise ComposeError(f"{what} source not found: {path}")


def _require_filters(ffmpeg: str, t: Timeline) -> None:
    needed: dict[str, tuple[str, str]] = {}
    if any(beat.text for beat in t.beats):
        needed["drawtext"] = ("text overlays", "--enable-libfreetype")
    if t.subtitles.mode == "burn":
        needed["subtitles"] = ("burned-in subtitles", "--enable-libass")
    if not needed:
        return
    available = _available_filters(ffmpeg)
    if not available:
        return  # the filter list could not be read; let ffmpeg say why itself
    for name, (why, flag) in sorted(needed.items()):
        if name not in available:
            raise ComposeError(
                f"this ffmpeg build has no '{name}' filter, which {why} need; "
                f"install an ffmpeg built with {flag}"
            )


@lru_cache(maxsize=8)
def _available_filters(ffmpeg: str) -> frozenset[str]:
    proc = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True)
    if proc.returncode != 0:
        return frozenset()
    return frozenset(
        m.group(1) for line in proc.stdout.splitlines() if (m := _FILTER_LINE.match(line))
    )


def _drawtext(text: TextOverlay, height: int) -> str:
    size = max(12, round(height / 20))
    opts = [
        f"text={_escape(text.content)}",
        "expansion=none",  # the caption is data, never a %{} template
        f"fontsize={size}",
        "fontcolor=white",
        "box=1",
        "boxcolor=black@0.5",
        f"boxborderw={max(4, size // 3)}",
        "x=(w-text_w)/2",
        f"y={_TEXT_Y[text.pos]}",
    ]
    font = _font_file()
    if font:
        opts.insert(0, f"fontfile={_escape(font)}")
    return "drawtext=" + ":".join(opts)


def _font_file() -> str | None:
    override = os.environ.get("VIRALPRINTER_FONT")
    if override:
        return override
    return next((p for p in _FONT_CANDIDATES if Path(p).exists()), None)


def _escape(value: str) -> str:
    """Escape a string for a filter option inside a filtergraph description.

    Two parsers see it: the filter's own option splitter, then the filtergraph
    splitter. Each consumes one level, so both are applied in order.
    """
    first = value.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    second = first.replace("\\", "\\\\").replace("'", "\\'")
    for ch in ",;[]":
        second = second.replace(ch, "\\" + ch)
    return second


def _num(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"


def _tail(stderr: str) -> str:
    lines = [line for line in (stderr or "").splitlines() if line.strip()]
    return "\n".join(lines[-_STDERR_TAIL_LINES:])
