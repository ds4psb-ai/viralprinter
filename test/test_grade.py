"""Grader tests: timeline mode on inline fixtures, video mode on a generated clip."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from viralprinter.grade import (
    CATEGORIES,
    GradeError,
    Scorecard,
    grade_timeline,
    grade_video,
    load_rules,
)

# --------------------------------------------------------------------------- fixtures

# 15.0s, five beats, hook opens at 0.0 and resolves in 1.5s, all required roles present.
COMPLETE = {
    "version": "0.1",
    "canvas": {"aspect": "9:16", "resolution": [1080, 1920], "fps": 30},
    "beats": [
        {
            "id": "hook",
            "role": "hook",
            "t": [0.0, 1.5],
            "shot": {"src": "clips/01.mp4", "in": 3.4, "framing": "close"},
            "text": {"content": "wait for it", "pos": "center"},
        },
        {
            "id": "dev1",
            "role": "development",
            "t": [1.5, 5.5],
            "shot": {"src": "clips/02.mp4"},
            "text": {"content": "step one", "pos": "top"},
        },
        {"id": "dev2", "role": "development", "t": [5.5, 10.0], "shot": {"src": "clips/03.mp4"}},
        {
            "id": "payoff",
            "role": "payoff",
            "t": [10.0, 13.0],
            "shot": {"src": "clips/04.mp4"},
            "text": {"content": "there it is", "pos": "center"},
        },
        {
            "id": "cta",
            "role": "cta",
            "t": [13.0, 15.0],
            "shot": {"src": "clips/05.mp4"},
            "text": {"content": "follow for more", "pos": "bottom"},
        },
    ],
    "subtitles": {"mode": "none"},
    "provenance": {"packet": "shorti-packet-complete.md"},
}

# 12.0s, hook arrives at 3.0s, no payoff role, and burned-in subtitles the beats do not enumerate.
BROKEN = {
    "version": "0.1",
    "canvas": {"aspect": "9:16", "resolution": [1080, 1920], "fps": 30},
    "beats": [
        {"id": "intro", "role": "other", "t": [0.0, 3.0], "shot": {"src": "clips/01.mp4"}},
        {
            "id": "hook",
            "role": "hook",
            "t": [3.0, 4.5],
            "shot": {"src": "clips/02.mp4"},
            "text": {"content": "here is the thing", "pos": "center"},
        },
        {"id": "dev", "role": "development", "t": [4.5, 9.0], "shot": {"src": "clips/03.mp4"}},
        {"id": "outro", "role": "other", "t": [9.0, 12.0], "shot": {"src": "clips/04.mp4"}},
    ],
    "subtitles": {"mode": "auto"},
}


def by_name(card: Scorecard) -> dict[str, object]:
    return {c.name: c for c in card.categories}


# --------------------------------------------------------------------------- rules


def test_rules_cover_every_category_as_provisional():
    rules = load_rules()
    assert set(rules) == set(CATEGORIES)
    for name, rule in rules.items():
        assert rule["provenance"] == "provisional", name
        assert rule["why"].strip(), name
        assert rule["band"], name


# --------------------------------------------------------------------------- timeline mode


def test_complete_timeline_lands_in_band_everywhere():
    card = grade_timeline(COMPLETE)
    rows = by_name(card)

    assert card.mode == "timeline"
    assert [c.name for c in card.categories] == list(CATEGORIES)
    assert all(c.state == "measured" for c in card.categories)
    assert all(c.verdict == "in_band" for c in card.categories)

    assert rows["hook_window"].measured == {"onset": 0.0, "length": 1.5}
    assert rows["duration_fit"].measured == pytest.approx(15.0)
    assert rows["cut_cadence"].measured == pytest.approx(5 / 15 * 10, abs=1e-3)
    assert rows["cut_cadence"].band["duration_class"] == "short"
    assert rows["structure_completeness"].measured == ["cta", "development", "hook", "payoff"]
    assert rows["text_density"].measured == pytest.approx(111.5 / 15, abs=1e-3)


def test_broken_timeline_flags_late_hook_and_missing_payoff():
    card = grade_timeline(BROKEN)
    rows = by_name(card)

    assert rows["hook_window"].state == "measured"
    assert rows["hook_window"].measured == {"onset": 3.0, "length": 1.5}
    assert rows["hook_window"].verdict == "out_of_band"

    assert rows["structure_completeness"].verdict == "out_of_band"
    assert rows["structure_completeness"].measured == ["development", "hook", "other"]
    assert "payoff" in rows["structure_completeness"].why

    # The two defects the fixture encodes are the only two: everything else still passes.
    assert rows["duration_fit"].verdict == "in_band"
    assert rows["cut_cadence"].verdict == "in_band"


def test_burned_in_subtitles_make_text_density_an_honest_absence():
    row = by_name(grade_timeline(BROKEN))["text_density"]
    assert row.state == "not_measured"
    assert row.measured is None
    assert row.verdict is None
    assert "auto" in row.why
    assert row.band is not None  # the reader still sees what would have been checked


def test_unlabelled_timeline_is_not_measured_rather_than_incomplete():
    unlabelled = {
        "version": "0.1",
        "beats": [
            {"id": "a", "t": [0.0, 4.0], "shot": {"src": "clips/01.mp4"}},
            {"id": "b", "t": [4.0, 9.0], "shot": {"src": "clips/02.mp4"}},
        ],
    }
    rows = by_name(grade_timeline(unlabelled))
    for name in ("hook_window", "structure_completeness"):
        assert rows[name].state == "not_measured", name
        assert rows[name].verdict is None, name
    assert rows["duration_fit"].state == "measured"


def test_timeline_accepts_an_object_exposing_its_raw_dict():
    class Timelineish:
        raw = COMPLETE

    assert grade_timeline(Timelineish()).to_dict() == grade_timeline(COMPLETE).to_dict()


@pytest.mark.parametrize(
    "bad",
    [
        {"version": "0.1"},  # no beats key
        {"version": "0.1", "beats": []},  # empty beats
        {"version": "0.1", "beats": [{"id": "a", "shot": {}}]},  # beat without t
        {"version": "0.1", "beats": [{"id": "a", "t": [0.0, "x"]}]},  # non-numeric t
        {"version": "0.1", "beats": [{"id": "a", "t": [4.0, 1.0]}]},  # ends before it starts
    ],
)
def test_unreadable_timeline_raises_grade_error(bad):
    with pytest.raises(GradeError):
        grade_timeline(bad)


def test_non_timeline_input_raises_grade_error():
    with pytest.raises(GradeError):
        grade_timeline(object())


def test_renderers_show_state_verdict_and_the_provisional_caveat():
    card = grade_timeline(BROKEN)
    for text in (card.render_markdown(), card.render_terminal()):
        assert "text_density" in text
        assert "not_measured" in text
        assert "out_of_band" in text
        assert "provisional" in text
    assert card.render_markdown().count("|") > 20  # a real table, not a paragraph
    assert "\n" in card.render_terminal()


# --------------------------------------------------------------------------- video mode

pytestmark_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not on PATH",
)


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    """8s 320x568 clip: 4s of testsrc then 4s of smptebars, so scdet sees one cut at 4s."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    out = tmp_path_factory.mktemp("clips") / "two-shots.mp4"
    cp = subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=4",
            "-f", "lavfi", "-i", "smptebars=size=320x568:rate=30:duration=4",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if cp.returncode != 0 or not out.is_file():
        pytest.skip(f"could not generate the test clip:\n{cp.stderr.strip()[-800:]}")
    return out


@pytestmark_ffmpeg
def test_video_mode_measures_duration_cadence_and_hook(clip):
    card = grade_video(clip)
    rows = by_name(card)

    assert card.mode == "video"
    assert [c.name for c in card.categories] == list(CATEGORIES)

    assert rows["duration_fit"].state == "measured"
    assert rows["duration_fit"].measured == pytest.approx(8.0, abs=0.2)
    assert rows["duration_fit"].verdict == "in_band"

    # One cut at ~4s is what the fixture is built to produce; detection must find it.
    assert rows["cut_cadence"].state == "measured"
    assert rows["cut_cadence"].measured > 0, "scdet found no cut in a two-shot clip"
    assert rows["cut_cadence"].band["duration_class"] == "short"

    assert rows["hook_window"].state == "measured"
    assert 3.0 <= rows["hook_window"].measured <= 5.0
    assert rows["hook_window"].verdict == "out_of_band"  # first cut lands well past 2.0s


@pytest.fixture(scope="module")
def single_shot(tmp_path_factory):
    """9s 320x568 clip of one flat colour: nothing for scdet to find."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    out = tmp_path_factory.mktemp("clips") / "one-shot.mp4"
    cp = subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=navy:size=320x568:rate=30:duration=9",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if cp.returncode != 0 or not out.is_file():
        pytest.skip(f"could not generate the test clip:\n{cp.stderr.strip()[-800:]}")
    return out


@pytestmark_ffmpeg
def test_single_shot_clip_reports_duration_not_a_phantom_cut(single_shot):
    rows = by_name(grade_video(single_shot))
    assert rows["cut_cadence"].measured == 0.0
    # With no cut anywhere, hook_window falls back to the duration, and says so.
    assert rows["hook_window"].measured == pytest.approx(9.0, abs=0.2)
    assert "not a cut time" in rows["hook_window"].why


def test_a_silent_empty_scdet_run_is_an_error_not_zero_cuts(tmp_path, monkeypatch):
    """ffmpeg exiting 0 while writing no report is an instrument failure, not a cutless video."""
    import viralprinter.grade as grade

    monkeypatch.setattr(
        grade, "_run", lambda cmd: subprocess.CompletedProcess(cmd, 0, "", "a warning\n")
    )
    clip = tmp_path / "x.mp4"
    clip.write_bytes(b"x")
    with pytest.raises(GradeError, match="instrument failure"):
        grade._detect_cuts(clip)


@pytestmark_ffmpeg
def test_video_mode_reports_roles_and_text_as_honest_absences(clip):
    rows = by_name(grade_video(clip))
    for name in ("structure_completeness", "text_density"):
        row = rows[name]
        assert row.state == "not_measured", name
        assert row.measured is None, name
        assert row.verdict is None, name
        assert len(row.why.split()) >= 8, f"{name} absence needs a real reason"


@pytestmark_ffmpeg
def test_video_scorecard_serialises_and_renders(clip):
    card = grade_video(clip)
    payload = card.to_dict()
    assert payload["mode"] == "video"
    assert [c["name"] for c in payload["categories"]] == list(CATEGORIES)

    terminal = card.render_terminal()
    header, rule = terminal.splitlines()[3], terminal.splitlines()[4]
    assert header.startswith("CATEGORY")
    assert set(rule) <= {"-", " "}  # the columns are aligned by an ASCII rule, no color deps


def test_missing_file_raises_grade_error(tmp_path):
    with pytest.raises(GradeError):
        grade_video(tmp_path / "nope.mp4")
