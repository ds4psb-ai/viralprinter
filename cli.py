"""viralprinter command line: validate, compose, grade."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

# The six fields DESIGN.md freezes for a CategoryResult; --json is built from
# them so the grader owns its own shape without owning a serializer.
_CATEGORY_FIELDS = ("name", "state", "measured", "band", "verdict", "why")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="viralprinter",
        description="Compose short-form video from a timeline, and grade any short against viral-structure rules.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="check a timeline against the v0.1 contract")
    p_validate.add_argument("timeline", type=Path)

    p_compose = sub.add_parser("compose", help="render a timeline to mp4 with ffmpeg")
    p_compose.add_argument("timeline", type=Path)
    p_compose.add_argument("-o", "--out", required=True, type=Path, help="output mp4 path")
    p_compose.add_argument(
        "--dry-run", action="store_true", help="print the ffmpeg command that would run, render nothing"
    )

    p_grade = sub.add_parser("grade", help="score an mp4 or a timeline against viral-structure rules")
    p_grade.add_argument("target", type=Path, help="a video file, or a timeline .json")
    output = p_grade.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="machine-readable scorecard")
    output.add_argument("--markdown", action="store_true", help="markdown scorecard")

    args = parser.parse_args(argv)
    return {"validate": _validate, "compose": _compose, "grade": _grade}[args.command](args)


def _validate(args: argparse.Namespace) -> int:
    from viralprinter.timeline import TimelineError, load

    try:
        timeline = load(args.timeline)
    except TimelineError as e:
        print(e, file=sys.stderr)
        return 1
    canvas = timeline.canvas
    print(
        f"ok: {args.timeline}: {len(timeline.beats)} beats, {timeline.duration:.2f}s, "
        f"{canvas.width}x{canvas.height} @ {canvas.fps:g}fps"
    )
    return 0


def _compose(args: argparse.Namespace) -> int:
    from viralprinter.compose import ComposeError, render
    from viralprinter.timeline import TimelineError, load

    try:
        result = render(load(args.timeline), args.out, dry_run=args.dry_run)
    except (TimelineError, ComposeError) as e:
        print(e, file=sys.stderr)
        return 1
    print(shlex.join(result) if args.dry_run else result)
    return 0


def _grade(args: argparse.Namespace) -> int:
    # Imported here so validate and compose work while the grader is mid-build.
    try:
        from viralprinter.grade import grade_timeline, grade_video
    except Exception as e:  # noqa: BLE001 - any import-time failure is the same answer here
        print(f"viralprinter grade is unavailable: {_one_line(e)}", file=sys.stderr)
        return 2

    target: Path = args.target
    if not target.exists():
        print(f"no such file: {target}", file=sys.stderr)
        return 1

    try:
        if target.suffix.lower() == ".json":
            from viralprinter.timeline import load

            card = grade_timeline(load(target))
        else:
            card = grade_video(target)
    except Exception as e:  # noqa: BLE001 - report, never traceback at the CLI edge
        print(f"grade failed on {target}: {_one_line(e)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"categories": [_category_dict(c) for c in card.categories]}, indent=2, default=str))
    elif args.markdown:
        print(card.render_markdown())
    else:
        print(card.render_terminal())
    return 0


def _category_dict(category: object) -> dict[str, object]:
    return {field: getattr(category, field, None) for field in _CATEGORY_FIELDS}


def _one_line(e: Exception) -> str:
    first = str(e).strip().splitlines()
    return f"{type(e).__name__}: {first[0] if first else e!r}"


if __name__ == "__main__":
    raise SystemExit(main())
