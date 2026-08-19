"""Compose: render real (tiny) media and check what came out.

Test clips are generated with ffmpeg lavfi, so nothing binary is committed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from viralprinter.compose import ComposeError, _available_filters, _escape, render
from viralprinter.timeline import Timeline

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(
    not (FFMPEG and FFPROBE),
    reason="ffmpeg and ffprobe are not on PATH; compose tests generate their own media",
)

WIDTH, HEIGHT, FPS = 320, 568, 30
CLIP_SECONDS = 2.0


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def _clip(path: Path, seconds: float = CLIP_SECONDS) -> Path:
    _run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "lavfi", "-i", f"testsrc=size={WIDTH}x{HEIGHT}:rate={FPS}:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ])
    return path


def _probe(path: Path) -> dict:
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
         "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def clips(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A directory holding 01.mp4 and 02.mp4, both silent testsrc."""
    d = tmp_path_factory.mktemp("clips")
    _clip(d / "01.mp4")
    _clip(d / "02.mp4")
    return d


def two_beats(base_dir: Path, **over: object) -> Timeline:
    doc = {
        "version": "0.1",
        "canvas": {"aspect": "9:16", "resolution": [WIDTH, HEIGHT], "fps": FPS},
        "beats": [
            {"id": "hook", "role": "hook", "t": [0.0, 1.0], "shot": {"src": "01.mp4", "in": 0.2}},
            {"id": "payoff", "role": "payoff", "t": [1.0, 2.5], "shot": {"src": "02.mp4", "in": 0.0}},
        ],
    }
    doc.update(over)
    return Timeline.from_dict(doc, base_dir=base_dir)


def assert_video(path: Path, *, seconds: float) -> dict:
    info = _probe(path)
    assert abs(float(info["format"]["duration"]) - seconds) <= 0.3, info["format"]
    video = [s for s in info["streams"] if s["codec_type"] == "video"]
    assert len(video) == 1 and (video[0]["width"], video[0]["height"]) == (WIDTH, HEIGHT)
    return info


def test_renders_two_beats(clips: Path, tmp_path: Path):
    out = render(two_beats(clips), tmp_path / "out.mp4")
    assert out.exists()
    assert_video(out, seconds=2.5)


def test_output_directory_is_created(clips: Path, tmp_path: Path):
    out = render(two_beats(clips), tmp_path / "nested" / "dir" / "out.mp4")
    assert out.exists()


def test_silent_sources_still_get_an_audio_track(clips: Path, tmp_path: Path):
    info = _probe(render(two_beats(clips), tmp_path / "out.mp4"))
    assert [s["codec_type"] for s in info["streams"]].count("audio") == 1


def test_music_is_mixed_in(clips: Path, tmp_path: Path):
    music = tmp_path / "music.wav"
    _run([FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
          "-f", "lavfi", "-i", "sine=frequency=440:duration=4", str(music)])
    timeline = two_beats(clips, audio={"music": {"src": str(music), "gain_db": -18}})
    info = assert_video(render(timeline, tmp_path / "out.mp4"), seconds=2.5)
    # Music longer than the video must not extend it.
    assert [s["codec_type"] for s in info["streams"]].count("audio") == 1


def test_a_gap_between_beats_holds_absolute_time(clips: Path, tmp_path: Path):
    timeline = two_beats(clips, beats=[
        {"id": "hook", "role": "hook", "t": [0.0, 1.0], "shot": {"src": "01.mp4"}},
        {"id": "payoff", "role": "payoff", "t": [1.5, 2.5], "shot": {"src": "02.mp4"}},
    ])
    assert_video(render(timeline, tmp_path / "out.mp4"), seconds=2.5)


def test_a_leading_gap_holds_absolute_time(clips: Path, tmp_path: Path):
    timeline = two_beats(clips, beats=[
        {"id": "late", "role": "hook", "t": [0.5, 1.5], "shot": {"src": "01.mp4"}},
    ])
    assert_video(render(timeline, tmp_path / "out.mp4"), seconds=1.5)


def test_dry_run_plans_without_writing(clips: Path, tmp_path: Path):
    out = tmp_path / "out.mp4"
    cmd = render(two_beats(clips), out, dry_run=True)

    assert isinstance(cmd, list) and Path(cmd[0]).name == "ffmpeg"
    assert not out.exists()
    assert cmd[-1] == str(out)
    assert cmd.count("-i") == 2
    for flag in ("-y", "-filter_complex", "libx264", "aac", "yuv420p"):
        assert flag in cmd, flag

    graph = cmd[cmd.index("-filter_complex") + 1]
    assert graph.count("concat=n=2:v=1:a=1") == 1
    assert f"scale={WIDTH}:{HEIGHT}" in graph


def test_dry_run_works_without_the_sources(tmp_path: Path):
    timeline = two_beats(tmp_path / "gone")
    cmd = render(timeline, tmp_path / "out.mp4", dry_run=True)
    assert isinstance(cmd, list)


def test_missing_source_is_refused(tmp_path: Path):
    with pytest.raises(ComposeError, match="shot source not found"):
        render(two_beats(tmp_path / "gone"), tmp_path / "out.mp4")


def test_a_shot_too_short_for_its_beat_is_refused(clips: Path, tmp_path: Path):
    timeline = two_beats(clips, beats=[
        {"id": "hook", "role": "hook", "t": [0.0, 3.0], "shot": {"src": "01.mp4", "in": 0.5}},
    ])
    with pytest.raises(ComposeError, match="needs 3.50s of 01.mp4"):
        render(timeline, tmp_path / "out.mp4")


def test_missing_music_is_refused(clips: Path, tmp_path: Path):
    timeline = two_beats(clips, audio={"music": {"src": "gone.mp3"}})
    with pytest.raises(ComposeError, match="music source not found"):
        render(timeline, tmp_path / "out.mp4")


def test_burn_subtitles_are_planned_from_the_srt(clips: Path, tmp_path: Path):
    srt = clips / "subs.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    cmd = render(two_beats(clips, subtitles={"mode": "burn", "src": "subs.srt"}), tmp_path / "out.mp4", dry_run=True)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert f"subtitles=filename={_escape(str(srt))}" in graph
    assert "-map" in cmd and "[vsub]" in cmd


def test_burn_without_a_source_is_refused_even_when_hand_built(clips: Path, tmp_path: Path):
    from dataclasses import replace

    from viralprinter.timeline import Subtitles

    timeline = replace(two_beats(clips), subtitles=Subtitles(mode="burn"))
    with pytest.raises(ComposeError, match="needs subtitles.src"):
        render(timeline, tmp_path / "out.mp4", dry_run=True)


def test_text_overlay_is_planned_with_escaped_text(clips: Path, tmp_path: Path):
    caption = "it's a 'hook': one, or more [special] chars"
    timeline = two_beats(clips, beats=[
        {"id": "hook", "role": "hook", "t": [0.0, 1.0], "shot": {"src": "01.mp4"},
         "text": {"content": caption, "pos": "bottom"}},
    ])
    graph = render(timeline, tmp_path / "out.mp4", dry_run=True)[1:]
    graph = [a for a in graph if a.startswith("[0:v]")][0]
    assert "drawtext=" in graph and "expansion=none" in graph
    assert caption not in graph  # the raw caption would break the filtergraph


def test_escaping_survives_both_filtergraph_parsers(tmp_path: Path):
    """drawtext is missing from builds without libfreetype, so the escaping is
    checked through metadata, which every build has and which prints back
    exactly what the two parsers delivered."""
    hostile = "it's a 'string': one, or more [special]; chars \\ here"
    out = tmp_path / "meta.txt"
    _run([
        FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "lavfi", "-i", "testsrc=size=64x64:rate=1:duration=1",
        "-vf", f"metadata=mode=add:key=caption:value={_escape(hostile)},"
               f"metadata=mode=print:file={out}",
        "-f", "null", "-",
    ])
    printed = [line for line in out.read_text(encoding="utf-8").splitlines() if "caption=" in line]
    assert printed and printed[0].split("caption=", 1)[1] == hostile


@pytest.mark.skipif(
    FFMPEG is not None and "drawtext" not in _available_filters(FFMPEG),
    reason="this ffmpeg build has no drawtext filter (built without libfreetype)",
)
def test_renders_a_text_overlay(clips: Path, tmp_path: Path):
    timeline = two_beats(clips, beats=[
        {"id": "hook", "role": "hook", "t": [0.0, 1.0], "shot": {"src": "01.mp4"},
         "text": {"content": "wait for it", "pos": "center"}},
    ])
    assert_video(render(timeline, tmp_path / "out.mp4"), seconds=1.0)


def test_a_build_without_drawtext_says_so(clips: Path, tmp_path: Path):
    if "drawtext" in _available_filters(FFMPEG):
        pytest.skip("this ffmpeg build has drawtext, so there is nothing to refuse")
    timeline = two_beats(clips, beats=[
        {"id": "hook", "role": "hook", "t": [0.0, 1.0], "shot": {"src": "01.mp4"},
         "text": {"content": "wait for it"}},
    ])
    with pytest.raises(ComposeError, match="no 'drawtext' filter"):
        render(timeline, tmp_path / "out.mp4")
