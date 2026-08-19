"""Timeline v0.1: what the contract accepts, and what it refuses to guess at."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from viralprinter.timeline import SCHEMA, Timeline, TimelineError, load, validate

DESIGN_EXAMPLE = {
    "version": "0.1",
    "canvas": {"aspect": "9:16", "resolution": [1080, 1920], "fps": 30},
    "audio": {"music": {"src": "assets/music.mp3", "gain_db": -18}},
    "beats": [
        {
            "id": "hook",
            "role": "hook",
            "t": [0.0, 1.2],
            "shot": {"src": "clips/01.mp4", "in": 3.4, "framing": "close"},
            "text": {"content": "wait for it", "pos": "center"},
            "cue": "cold open on the reveal, no logo",
        }
    ],
    "subtitles": {"mode": "none"},
    "provenance": {"packet": "shorti-packet-slug.md"},
}


def beat(start: float, end: float, **over: object) -> dict:
    b = {"id": f"b{start:g}", "role": "development", "t": [start, end], "shot": {"src": "clips/01.mp4"}}
    b.update(over)
    return b


def timeline(*beats: dict, **over: object) -> dict:
    doc = {
        "version": "0.1",
        "canvas": {"aspect": "9:16", "resolution": [1080, 1920], "fps": 30},
        "beats": list(beats) or [beat(0.0, 1.2)],
    }
    doc.update(over)
    return doc


def only_error(doc: dict) -> str:
    errors = validate(doc)
    assert len(errors) == 1, errors
    return errors[0]


def test_design_example_is_valid():
    assert validate(DESIGN_EXAMPLE) == []


def test_minimal_timeline_is_valid():
    assert validate({"version": "0.1", "canvas": {"resolution": [1080, 1920], "fps": 30}, "beats": [beat(0, 1)]}) == []


def test_schema_is_bundled_and_describes_v01():
    assert SCHEMA["properties"]["version"]["const"] == "0.1"


def test_overlapping_beats_are_refused():
    assert "overlaps" in only_error(timeline(beat(0.0, 1.5), beat(1.0, 2.0)))


def test_unsorted_beats_are_refused():
    assert "sorted" in only_error(timeline(beat(2.0, 3.0), beat(0.0, 1.0)))


def test_touching_beats_are_fine():
    assert validate(timeline(beat(0.0, 1.0), beat(1.0, 2.0))) == []


def test_a_gap_between_beats_is_allowed():
    assert validate(timeline(beat(0.0, 1.0), beat(1.5, 2.0))) == []


def test_zero_length_beat_is_refused():
    assert "greater than start" in only_error(timeline(beat(1.0, 1.0)))


def test_unknown_role_is_refused():
    assert "role" in only_error(timeline(beat(0.0, 1.0, role="teaser")))


def test_missing_shot_is_refused():
    assert only_error(timeline({"id": "a", "t": [0.0, 1.0]})) == "$.beats[0]: 'shot' is a required property"


def test_missing_t_is_refused():
    assert "'t' is a required property" in only_error(timeline({"id": "a", "shot": {"src": "a.mp4"}}))


def test_negative_time_is_refused():
    assert "$.beats[0].t[0]" in only_error(timeline(beat(-1.0, 1.0)))


def test_unknown_key_is_refused_rather_than_dropped():
    assert "hook_strength" in only_error(timeline(beat(0.0, 1.0), hook_strength=0.8))


def test_unknown_beat_key_is_refused_rather_than_dropped():
    assert "zoom" in only_error(timeline(beat(0.0, 1.0, zoom=1.2)))


def test_odd_resolution_is_refused():
    doc = timeline(canvas={"resolution": [1081, 1920], "fps": 30})
    assert "multiple of 2" in only_error(doc)


def test_burn_subtitles_need_a_source():
    assert "requires 'src'" in only_error(timeline(subtitles={"mode": "burn"}))


def test_burn_subtitles_with_a_source_are_valid():
    assert validate(timeline(subtitles={"mode": "burn", "src": "subs.srt"})) == []


def test_a_non_object_is_refused():
    assert "must be a JSON object" in only_error([])


def test_every_error_is_reported_at_once():
    doc = timeline(beat(0.0, 1.0, role="teaser"), canvas={"resolution": [1080, 1921], "fps": 0})
    assert len(validate(doc)) == 3


def test_typed_access(tmp_path: Path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps(DESIGN_EXAMPLE), encoding="utf-8")
    t = load(path)

    assert t.version == "0.1"
    assert (t.canvas.width, t.canvas.height, t.canvas.fps, t.canvas.aspect) == (1080, 1920, 30, "9:16")
    assert t.duration == 1.2
    assert t.subtitles.mode == "none"
    assert t.audio is not None and t.audio.music is not None
    assert (t.audio.music.src, t.audio.music.gain_db) == ("assets/music.mp3", -18)
    assert t.provenance == {"packet": "shorti-packet-slug.md"}

    (b,) = t.beats
    assert (b.id, b.role, b.start, b.end, b.duration) == ("hook", "hook", 0.0, 1.2, 1.2)
    assert (b.shot.src, b.shot.in_point, b.shot.framing) == ("clips/01.mp4", 3.4, "close")
    assert b.text is not None and (b.text.content, b.text.pos) == ("wait for it", "center")
    assert b.cue == "cold open on the reveal, no logo"


def test_defaults_are_filled_from_the_contract():
    t = Timeline.from_dict(timeline({"t": [0.0, 1.0], "shot": {"src": "a.mp4"}}))
    (b,) = t.beats
    assert (b.role, b.id, b.text, b.cue, b.shot.in_point) == ("other", None, None, None, 0.0)
    assert (t.subtitles.mode, t.audio, t.provenance) == ("none", None, {})


def test_assets_resolve_against_the_timeline_file(tmp_path: Path):
    path = tmp_path / "deep" / "t.json"
    path.parent.mkdir()
    path.write_text(json.dumps(DESIGN_EXAMPLE), encoding="utf-8")
    t = load(path)
    assert t.resolve("clips/01.mp4") == tmp_path / "deep" / "clips" / "01.mp4"
    assert t.resolve("/abs/01.mp4") == Path("/abs/01.mp4")


def test_load_carries_every_error(tmp_path: Path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps(timeline(beat(0.0, 1.5), beat(1.0, 2.0))), encoding="utf-8")
    with pytest.raises(TimelineError) as excinfo:
        load(path)
    assert excinfo.value.errors == ["$.beats[1].t: overlaps the previous beat (starts 1, previous beat ends 1.5)"]
    assert "overlaps" in str(excinfo.value)


def test_load_reports_where_the_json_broke(tmp_path: Path):
    path = tmp_path / "t.json"
    path.write_text('{"version": "0.1",}', encoding="utf-8")
    with pytest.raises(TimelineError, match="invalid JSON at line 1"):
        load(path)


def test_load_reports_a_missing_file(tmp_path: Path):
    with pytest.raises(TimelineError, match="cannot read timeline"):
        load(tmp_path / "nope.json")


def test_to_dict_does_not_alias_the_timeline():
    t = Timeline.from_dict(DESIGN_EXAMPLE)
    t.to_dict()["beats"].clear()
    assert len(t.beats) == 1
