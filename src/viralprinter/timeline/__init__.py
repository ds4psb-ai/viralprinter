"""Timeline v0.1 - shorts-as-code: load, validate, and typed access.

The wire format is JSON and its contract is `schema.json`, shipped beside this
module so other tools can consume it. Rules the schema cannot express - beats
sorted and non-overlapping, burn-in subtitles needing a source - live in
`validate()`.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

__all__ = [
    "ROLES",
    "SCHEMA",
    "Audio",
    "Beat",
    "Canvas",
    "Music",
    "Shot",
    "Subtitles",
    "TextOverlay",
    "Timeline",
    "TimelineError",
    "load",
    "validate",
]

ROLES = ("hook", "development", "payoff", "cta", "other")

SCHEMA: dict[str, Any] = json.loads(
    (resources.files(__package__) / "schema.json").read_text(encoding="utf-8")
)

_VALIDATOR = Draft202012Validator(SCHEMA)

# Beat boundaries are authored by hand and by models; compare them with a
# tolerance well under one frame at 240fps.
_EPS = 1e-6


class TimelineError(ValueError):
    """A timeline could not be read or does not satisfy the v0.1 contract."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = list(errors or [])
        detail = "".join(f"\n  - {e}" for e in self.errors)
        super().__init__(f"{message}{detail}")


@dataclass(frozen=True, slots=True)
class Canvas:
    resolution: tuple[int, int]
    fps: float
    aspect: str | None = None

    @property
    def width(self) -> int:
        return self.resolution[0]

    @property
    def height(self) -> int:
        return self.resolution[1]


@dataclass(frozen=True, slots=True)
class Shot:
    src: str
    in_point: float = 0.0
    framing: str | None = None


@dataclass(frozen=True, slots=True)
class TextOverlay:
    content: str
    pos: str = "center"


@dataclass(frozen=True, slots=True)
class Beat:
    t: tuple[float, float]
    shot: Shot
    id: str | None = None
    role: str = "other"
    text: TextOverlay | None = None
    cue: str | None = None

    @property
    def start(self) -> float:
        return self.t[0]

    @property
    def end(self) -> float:
        return self.t[1]

    @property
    def duration(self) -> float:
        return self.t[1] - self.t[0]

    @property
    def label(self) -> str:
        return self.id or f"{self.role}@{self.start:g}s"


@dataclass(frozen=True, slots=True)
class Music:
    src: str
    gain_db: float = 0.0


@dataclass(frozen=True, slots=True)
class Audio:
    music: Music | None = None


@dataclass(frozen=True, slots=True)
class Subtitles:
    mode: str = "none"
    src: str | None = None


@dataclass(frozen=True, slots=True)
class Timeline:
    version: str
    canvas: Canvas
    beats: tuple[Beat, ...]
    audio: Audio | None = None
    subtitles: Subtitles = Subtitles()
    provenance: dict[str, Any] = field(default_factory=dict)
    # Asset paths are relative to the timeline file, not to the working
    # directory, so a timeline and its clips move together.
    base_dir: Path = field(default_factory=Path.cwd)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, obj: dict[str, Any], *, base_dir: str | Path | None = None) -> Timeline:
        """Validate `obj` and build a Timeline. Raises TimelineError."""
        errors = validate(obj)
        if errors:
            raise TimelineError(f"{len(errors)} validation error(s)", errors)
        return cls._build(obj, Path(base_dir) if base_dir is not None else Path.cwd())

    @classmethod
    def _build(cls, obj: dict[str, Any], base_dir: Path) -> Timeline:
        canvas = obj["canvas"]
        audio = obj.get("audio")
        music = (audio or {}).get("music")
        subtitles = obj.get("subtitles") or {}
        return cls(
            version=obj["version"],
            canvas=Canvas(
                resolution=(canvas["resolution"][0], canvas["resolution"][1]),
                fps=canvas["fps"],
                aspect=canvas.get("aspect"),
            ),
            beats=tuple(_build_beat(b) for b in obj["beats"]),
            audio=Audio(music=Music(src=music["src"], gain_db=music.get("gain_db", 0.0)) if music else None)
            if audio is not None
            else None,
            subtitles=Subtitles(mode=subtitles.get("mode", "none"), src=subtitles.get("src")),
            provenance=copy.deepcopy(obj.get("provenance") or {}),
            base_dir=base_dir,
            raw=copy.deepcopy(obj),
        )

    @property
    def duration(self) -> float:
        """Absolute end of the last beat; gaps between beats count."""
        return self.beats[-1].end if self.beats else 0.0

    def resolve(self, src: str) -> Path:
        """Absolute path of an asset referenced by this timeline."""
        p = Path(src).expanduser()
        return p if p.is_absolute() else (self.base_dir / p)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.raw)


def _build_beat(b: dict[str, Any]) -> Beat:
    shot = b["shot"]
    text = b.get("text")
    return Beat(
        t=(b["t"][0], b["t"][1]),
        shot=Shot(src=shot["src"], in_point=shot.get("in", 0.0), framing=shot.get("framing")),
        id=b.get("id"),
        role=b.get("role", "other"),
        text=TextOverlay(content=text["content"], pos=text.get("pos", "center")) if text else None,
        cue=b.get("cue"),
    )


def validate(obj: Any) -> list[str]:
    """Return every reason `obj` is not a valid timeline; [] when it is valid."""
    if not isinstance(obj, dict):
        return [f"$: timeline must be a JSON object, got {type(obj).__name__}"]
    errors = [
        f"{e.json_path}: {e.message}"
        for e in sorted(_VALIDATOR.iter_errors(obj), key=lambda e: (e.json_path, e.message))
    ]
    # Structural checks below index into the document, so they only run once the
    # schema says the shapes are there.
    return errors or _structural_errors(obj)


def _structural_errors(obj: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prev_start: float | None = None
    prev_end: float | None = None
    for i, beat in enumerate(obj["beats"]):
        start, end = beat["t"]
        if end - start <= _EPS:
            errors.append(f"$.beats[{i}].t: end {end:g} must be greater than start {start:g}")
        if prev_start is not None and start < prev_start - _EPS:
            errors.append(
                f"$.beats[{i}].t: beats must be sorted by start time "
                f"(starts {start:g}, previous beat starts {prev_start:g})"
            )
        elif prev_end is not None and start < prev_end - _EPS:
            errors.append(
                f"$.beats[{i}].t: overlaps the previous beat "
                f"(starts {start:g}, previous beat ends {prev_end:g})"
            )
        prev_start, prev_end = start, end

    subtitles = obj.get("subtitles") or {}
    if subtitles.get("mode") == "burn" and not subtitles.get("src"):
        errors.append("$.subtitles: mode 'burn' requires 'src', the path to an .srt file")
    return errors


def load(path: str | Path) -> Timeline:
    """Read a timeline JSON file, validate it, return a Timeline.

    Raises TimelineError for a missing file, malformed JSON, or any contract
    violation - the errors are on `TimelineError.errors`.
    """
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise TimelineError(f"{p}: cannot read timeline ({e.strerror or e})") from e
    except json.JSONDecodeError as e:
        raise TimelineError(f"{p}: invalid JSON at line {e.lineno} column {e.colno}: {e.msg}") from e

    errors = validate(raw)
    if errors:
        raise TimelineError(f"{p}: {len(errors)} validation error(s)", errors)
    return Timeline._build(raw, p.parent)
