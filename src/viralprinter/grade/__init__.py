"""Grade a short-form video, or a timeline, against viral-structure rules.

Two entry points, one result type. `grade_video` measures what pixels can carry
(duration, scene changes); `grade_timeline` measures what the authoring format
declares (roles, beat spans, text). Whatever a given input cannot answer comes
back as `state: not_measured` with the reason, never as a guessed number, and
there is no overall score: the card is the result.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "CATEGORIES",
    "CategoryResult",
    "GradeError",
    "Scorecard",
    "grade_timeline",
    "grade_video",
    "load_rules",
]

CATEGORIES = (
    "hook_window",
    "cut_cadence",
    "duration_fit",
    "structure_completeness",
    "text_density",
)

MEASURED = "measured"
NOT_MEASURED = "not_measured"
IN_BAND = "in_band"
OUT_OF_BAND = "out_of_band"

_RULES_PATH = Path(__file__).parent / "rules" / "structure.yaml"
_SCDET_THRESHOLD = 10.0  # scdet's own default; a frame scoring at or above it is a cut
_SUBPROCESS_TIMEOUT = 600
_UNIT_SUFFIX = {"seconds": "s", "cuts_per_10s": "/10s", "chars_on_screen": " chars"}


class GradeError(Exception):
    """Input that cannot be graded, or an external tool that failed."""


# --------------------------------------------------------------------------- rules


@lru_cache(maxsize=1)
def load_rules() -> dict[str, dict[str, Any]]:
    """The packaged v0 bands, keyed by category."""
    try:
        doc = yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GradeError(f"cannot read grader rules at {_RULES_PATH}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise GradeError(f"grader rules at {_RULES_PATH} are not valid YAML: {exc}") from exc

    entries = (doc or {}).get("rules") or []
    rules = {r["category"]: r for r in entries if isinstance(r, Mapping) and "category" in r}
    missing = [c for c in CATEGORIES if c not in rules]
    if missing:
        raise GradeError(f"grader rules at {_RULES_PATH} are missing: {', '.join(missing)}")
    return rules


def _rule(category: str) -> tuple[dict[str, Any], str]:
    r = load_rules()[category]
    return dict(r.get("band") or {}), _oneline(str(r.get("why", "")))


# --------------------------------------------------------------------------- result types


@dataclass(frozen=True)
class CategoryResult:
    """One row of a scorecard.

    `why` does double duty by design, because the frozen interface has no
    separate reason field: when `state` is "measured" it is the band's
    rationale, and when it is "not_measured" it is why the measurement was
    impossible on this input. `band` is populated either way, so a reader can
    see what would have been checked.
    """

    name: str
    state: str
    measured: Any
    band: dict[str, Any] | None
    verdict: str | None
    why: str


@dataclass(frozen=True)
class Scorecard:
    source: str
    mode: str  # "video" | "timeline"
    categories: list[CategoryResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "mode": self.mode,
            "categories": [asdict(c) for c in self.categories],
        }

    def render_markdown(self) -> str:
        head = "| category | state | measured | band | verdict | why |\n|---|---|---|---|---|---|"
        rows = [
            "| `{}` | {} | {} | {} | {} | {} |".format(
                c.name,
                c.state,
                _fmt_measured(c),
                _fmt_band(c.band),
                c.verdict or "-",
                _oneline(c.why),
            )
            for c in self.categories
        ]
        return "\n".join(
            [
                "# viralprinter scorecard",
                "",
                f"**source**: `{self.source}` — **mode**: {self.mode}",
                "",
                head,
                *rows,
                "",
                "Bands are provisional v0 placeholders, not measured thresholds. "
                "Rows marked `not_measured` are honest absences, not zeros.",
            ]
        )

    def render_terminal(self, width: int = 96) -> str:
        head = ("CATEGORY", "STATE", "MEASURED", "BAND", "VERDICT")
        rows = [
            (c.name, c.state, _fmt_measured(c), _fmt_band(c.band), c.verdict or "-")
            for c in self.categories
        ]
        widths = [max(len(r[i]) for r in (head, *rows)) for i in range(len(head))]

        def line(cells: Sequence[str]) -> str:
            return "  ".join(v.ljust(widths[i]) for i, v in enumerate(cells)).rstrip()

        out = [
            f"viralprinter scorecard ({self.mode} mode)",
            f"source: {self.source}",
            "",
            line(head),
            "  ".join("-" * w for w in widths),
            *(line(r) for r in rows),
            "",
            "why:",
        ]
        for c in self.categories:
            out.append(
                textwrap.fill(
                    _oneline(c.why),
                    width=width,
                    initial_indent=f"  {c.name}: ",
                    subsequent_indent="    ",
                )
            )
        out += ["", "Bands are provisional v0 placeholders, not measured thresholds."]
        return "\n".join(out)


# --------------------------------------------------------------------------- formatting


def _oneline(text: str) -> str:
    return " ".join(str(text).split())


def _fmt_num(value: float, unit: str | None) -> str:
    return f"{value:.2f}{_UNIT_SUFFIX.get(unit or '', '')}"


def _fmt_measured(c: CategoryResult) -> str:
    value, unit = c.measured, (c.band or {}).get("unit")
    if value is None:
        return "-"
    if isinstance(value, Mapping):  # hook_window in timeline mode
        return f"onset {_fmt_num(value['onset'], unit)}, length {_fmt_num(value['length'], unit)}"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) or "(none)"
    if isinstance(value, (int, float)):
        return _fmt_num(float(value), unit)
    return str(value)


def _fmt_band(band: dict[str, Any] | None) -> str:
    if not band:
        return "-"
    if "required_roles" in band:
        return "requires " + ", ".join(band["required_roles"])
    unit = _UNIT_SUFFIX.get(band.get("unit", ""), "")
    if "onset_max" in band:
        return (
            f"onset <= {band['onset_max']:g}{unit}, "
            f"length {band['length_min']:g}-{band['length_max']:g}{unit}"
        )
    low, high = band.get("min"), band.get("max")
    if low is not None and high is not None:
        span = f"{low:g}-{high:g}{unit}"
    elif low is not None:
        span = f">= {low:g}{unit}"
    elif high is not None:
        span = f"<= {high:g}{unit}"
    else:
        return "-"
    cls = band.get("duration_class")
    return f"{span} ({cls} clip)" if cls else span


# --------------------------------------------------------------------------- verdicts


def _verdict_range(value: float, band: Mapping[str, Any]) -> str:
    low, high = band.get("min"), band.get("max")
    ok = (low is None or value >= low) and (high is None or value <= high)
    return IN_BAND if ok else OUT_OF_BAND


def _verdict_hook(measured: Any, band: Mapping[str, Any]) -> str:
    if isinstance(measured, Mapping):
        onset, length = measured["onset"], measured["length"]
        ok = onset <= band["onset_max"] and band["length_min"] <= length <= band["length_max"]
    else:  # video mode measures onset only
        ok = float(measured) <= band["onset_max"]
    return IN_BAND if ok else OUT_OF_BAND


def _cadence_band(band: Mapping[str, Any], duration: float) -> dict[str, Any]:
    """The band for this clip's duration class, resolved so the card shows what was applied."""
    classes = band.get("duration_classes") or []
    for cls in classes:
        window = cls.get("duration") or {}
        low, high = window.get("min"), window.get("max")
        if (low is None or duration >= low) and (high is None or duration < high):
            break
    else:
        cls = classes[-1] if classes else {}
    return {
        "unit": band.get("unit"),
        "min": cls.get("min"),
        "max": cls.get("max"),
        "duration_class": cls.get("name"),
    }


# --------------------------------------------------------------------------- subprocess


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT, check=False
        )
    except FileNotFoundError as exc:
        raise GradeError(f"{cmd[0]} not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GradeError(f"{cmd[0]} timed out after {_SUBPROCESS_TIMEOUT}s") from exc


def _tail(stderr: str | None, lines: int = 12) -> str:
    text = (stderr or "").strip()
    return "\n".join(text.splitlines()[-lines:]) if text else "(no stderr)"


def _escape_filter_path(path: Path) -> str:
    """Escape a path for use as a filtergraph option value."""
    return re.sub(r"([\\':,\[\]=;])", r"\\\1", str(path))


def _probe_duration(path: Path) -> float:
    cp = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    if cp.returncode != 0:
        raise GradeError(f"ffprobe failed on {path}:\n{_tail(cp.stderr)}")
    raw = cp.stdout.strip()
    try:
        duration = float(raw)
    except ValueError as exc:
        raise GradeError(
            f"ffprobe reported no usable duration for {path} (got {raw!r}):\n{_tail(cp.stderr)}"
        ) from exc
    if duration <= 0:
        raise GradeError(f"ffprobe reported a non-positive duration for {path}: {duration}")
    return duration


_FRAME_RE = re.compile(r"^frame:\d+\s+pts:\S+\s+pts_time:(?P<t>-?[\d.]+(?:[eE][-+]?\d+)?)")
_SCORE_RE = re.compile(r"^lavfi\.scd\.score=(?P<score>\S+)")


def _detect_cuts(path: Path, threshold: float = _SCDET_THRESHOLD) -> list[float]:
    """Scene-change times in seconds, via ffmpeg's scdet filter.

    Scores are read from the metadata filter's own output file rather than from
    ffmpeg's log, so the parse survives a log-level change or a reworded log
    line. A run that parses zero frames is an instrument failure, not a video
    without cuts, and raises instead of reporting an empty list.
    """
    with tempfile.TemporaryDirectory(prefix="viralprinter-scdet-") as tmp:
        meta = Path(tmp) / "scdet.txt"
        cp = _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-an",
                "-vf",
                f"scdet=t={threshold:g},metadata=mode=print:file={_escape_filter_path(meta)}",
                "-f",
                "null",
                "-",
            ]
        )
        if cp.returncode != 0:
            raise GradeError(f"ffmpeg scene detection failed on {path}:\n{_tail(cp.stderr)}")
        report = meta.read_text(encoding="utf-8", errors="replace") if meta.is_file() else ""

    frames = 0
    at: float | None = None
    cuts: list[float] = []
    for line in report.splitlines():
        frame = _FRAME_RE.match(line)
        if frame:
            frames += 1
            at = float(frame["t"])
            continue
        score = _SCORE_RE.match(line)
        if score and at is not None:
            try:
                value = float(score["score"])
            except ValueError:
                continue
            if value >= threshold:
                cuts.append(at)
    if frames == 0:
        raise GradeError(
            f"ffmpeg scene detection read no frames from {path}; this is an instrument "
            f"failure, not a video without cuts:\n{_tail(cp.stderr)}"
        )
    return cuts


# --------------------------------------------------------------------------- video mode


def grade_video(path: str | Path) -> Scorecard:
    """Grade an encoded video. Roles and on-screen text are not pixel facts in v0."""
    src = Path(path)
    if not src.is_file():
        raise GradeError(f"not a readable file: {src}")

    duration = _probe_duration(src)
    cuts = _detect_cuts(src)

    hook_band, hook_why = _rule("hook_window")
    first_cut = cuts[0] if cuts else duration
    results = [
        CategoryResult(
            name="hook_window",
            state=MEASURED,
            measured=round(first_cut, 3),
            band=hook_band,
            verdict=_verdict_hook(first_cut, hook_band),
            why=hook_why
            if cuts
            else (
                "No scene change was detected anywhere in the clip, so the value shown is the "
                "clip duration: a lower bound on when a first cut could arrive, not a cut time."
            ),
        )
    ]

    cadence_band, cadence_why = _rule("cut_cadence")
    resolved = _cadence_band(cadence_band, duration)
    cadence = len(cuts) / duration * 10.0
    results.append(
        CategoryResult(
            name="cut_cadence",
            state=MEASURED,
            measured=round(cadence, 3),
            band=resolved,
            verdict=_verdict_range(cadence, resolved),
            why=cadence_why,
        )
    )

    duration_band, duration_why = _rule("duration_fit")
    results.append(
        CategoryResult(
            name="duration_fit",
            state=MEASURED,
            measured=round(duration, 3),
            band=duration_band,
            verdict=_verdict_range(duration, duration_band),
            why=duration_why,
        )
    )

    structure_band, _ = _rule("structure_completeness")
    results.append(
        CategoryResult(
            name="structure_completeness",
            state=NOT_MEASURED,
            measured=None,
            band=structure_band,
            verdict=None,
            why=(
                "Beat roles are an authoring fact, not a pixel fact: nothing in an encoded video "
                "says which shot was meant as hook, development, or payoff. Grade the timeline "
                "to measure this."
            ),
        )
    )

    text_band, _ = _rule("text_density")
    results.append(
        CategoryResult(
            name="text_density",
            state=NOT_MEASURED,
            measured=None,
            band=text_band,
            verdict=None,
            why=(
                "Reading on-screen text out of pixels needs OCR, which v0 does not ship. Grade "
                "the timeline instead, where the text is declared rather than inferred."
            ),
        )
    )

    return Scorecard(source=str(src), mode="video", categories=results)


# --------------------------------------------------------------------------- timeline mode


def _as_dict(t: Any) -> dict[str, Any]:
    """A timeline as a plain dict, without importing viralprinter.timeline."""
    if isinstance(t, Mapping):
        return dict(t)
    for attr in ("raw", "data"):
        candidate = getattr(t, attr, None)
        if isinstance(candidate, Mapping):
            return dict(candidate)
    to_dict = getattr(t, "to_dict", None)
    if callable(to_dict):
        candidate = to_dict()
        if isinstance(candidate, Mapping):
            return dict(candidate)
    raise GradeError(f"cannot read a timeline out of {type(t).__name__}")


def _beat_spans(beats: Sequence[Any]) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    for i, beat in enumerate(beats):
        if not isinstance(beat, Mapping):
            raise GradeError(f"beat {i} is not an object")
        window = beat.get("t")
        if (
            not isinstance(window, Sequence)
            or isinstance(window, (str, bytes))
            or len(window) != 2
        ):
            raise GradeError(f"beat {i} has no [start, end] t")
        try:
            start, end = float(window[0]), float(window[1])
        except (TypeError, ValueError) as exc:
            raise GradeError(f"beat {i} has a non-numeric t: {window!r}") from exc
        if end < start:
            raise GradeError(f"beat {i} ends before it starts: {window!r}")
        spans.append((start, end))
    return spans


def grade_timeline(t: Any) -> Scorecard:
    """Grade a timeline statically. Accepts a dict, or any object exposing one."""
    doc = _as_dict(t)
    beats = doc.get("beats")
    if not isinstance(beats, Sequence) or isinstance(beats, (str, bytes)) or not beats:
        raise GradeError("timeline has no beats to grade")

    spans = _beat_spans(beats)
    order = sorted(range(len(beats)), key=lambda i: spans[i][0])
    total = max(end for _, end in spans)
    if total <= 0:
        raise GradeError(f"timeline ends at {total}, so there is nothing to grade")

    results: list[CategoryResult] = []

    hook_band, hook_why = _rule("hook_window")
    hook = next((i for i in order if beats[i].get("role") == "hook"), None)
    if hook is None:
        results.append(
            CategoryResult(
                name="hook_window",
                state=NOT_MEASURED,
                measured=None,
                band=hook_band,
                verdict=None,
                why="No beat declares role=hook, so there is no hook onset to time.",
            )
        )
    else:
        start, end = spans[hook]
        measured = {"onset": round(start, 3), "length": round(end - start, 3)}
        results.append(
            CategoryResult(
                name="hook_window",
                state=MEASURED,
                measured=measured,
                band=hook_band,
                verdict=_verdict_hook(measured, hook_band),
                why=hook_why,
            )
        )

    cadence_band, cadence_why = _rule("cut_cadence")
    resolved = _cadence_band(cadence_band, total)
    cadence = len(beats) / total * 10.0
    results.append(
        CategoryResult(
            name="cut_cadence",
            state=MEASURED,
            measured=round(cadence, 3),
            band=resolved,
            verdict=_verdict_range(cadence, resolved),
            why=cadence_why,
        )
    )

    duration_band, duration_why = _rule("duration_fit")
    results.append(
        CategoryResult(
            name="duration_fit",
            state=MEASURED,
            measured=round(total, 3),
            band=duration_band,
            verdict=_verdict_range(total, duration_band),
            why=duration_why,
        )
    )

    structure_band, structure_why = _rule("structure_completeness")
    roles = sorted({str(b["role"]) for b in beats if isinstance(b.get("role"), str)})
    if not roles:
        results.append(
            CategoryResult(
                name="structure_completeness",
                state=NOT_MEASURED,
                measured=None,
                band=structure_band,
                verdict=None,
                why=(
                    "No beat declares a role, so the timeline says nothing about structure. "
                    "An unlabelled timeline is unmeasured here, not incomplete."
                ),
            )
        )
    else:
        missing = [r for r in structure_band["required_roles"] if r not in roles]
        results.append(
            CategoryResult(
                name="structure_completeness",
                state=MEASURED,
                measured=roles,
                band=structure_band,
                verdict=OUT_OF_BAND if missing else IN_BAND,
                why=(
                    f"Missing required role(s): {', '.join(missing)}. {structure_why}"
                    if missing
                    else structure_why
                ),
            )
        )

    text_band, text_why = _rule("text_density")
    subtitles = doc.get("subtitles")
    mode = subtitles.get("mode") if isinstance(subtitles, Mapping) else None
    if mode not in (None, "none"):
        results.append(
            CategoryResult(
                name="text_density",
                state=NOT_MEASURED,
                measured=None,
                band=text_band,
                verdict=None,
                why=(
                    f"subtitles.mode is {mode!r}, which puts text on screen that the timeline "
                    "does not enumerate, so any character count here would be a guess."
                ),
            )
        )
    else:
        char_seconds = 0.0
        for i, beat in enumerate(beats):
            text = beat.get("text")
            content = text.get("content") if isinstance(text, Mapping) else None
            if isinstance(content, str):
                start, end = spans[i]
                char_seconds += len(content) * (end - start)
        density = char_seconds / total
        results.append(
            CategoryResult(
                name="text_density",
                state=MEASURED,
                measured=round(density, 3),
                band=text_band,
                verdict=_verdict_range(density, text_band),
                why=text_why,
            )
        )

    provenance = doc.get("provenance")
    packet = provenance.get("packet") if isinstance(provenance, Mapping) else None
    return Scorecard(source=str(packet or "<timeline>"), mode="timeline", categories=results)
