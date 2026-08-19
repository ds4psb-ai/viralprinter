# viralint — design contract (v0)

Open-source **composer + grader** for short-form video. The private evidence
engine (Shorti) *designs*; this repo *renders and judges*. This file is the
contract every builder follows. When code and this file disagree during v0,
this file wins.

## What this repo is

1. **Timeline** — "shorts-as-code": a declarative JSON format for a short-form
   video (beats, shots, text, audio), with a schema and validator.
2. **Compose** — render a timeline to an mp4 with ffmpeg. Local, deterministic,
   no accounts.
3. **Grade** — score any short (an mp4, or a timeline statically) against
   viral-structure rules. Categories and bands live in `src/viralint/grade/rules/*.yaml`.
4. **SKILL.md** — the distribution surface: one paste into Claude Code / Cursor
   / any agent CLI drives the whole loop.

## Boundary ledger (non-negotiable)

- `grade/rules/*.yaml` is the ONLY artifact in this repo derived from the
  private corpus — and only as coarse categories and bands. Never corpus rows,
  embeddings, measurement schemas, prompt text, model names, or thresholds
  copied verbatim from private code. v0 bands are hand-set provisional values
  marked `provenance: provisional`; a future regeneration replaces them.
- No server-side secrets, ever. Provider adapters (`providers/`) take user keys
  from the user's environment, run client-side, and never transmit keys
  anywhere except the provider's own API.
- The repo must run fully offline except: (a) explicit provider render calls,
  (b) the optional `shorti/` bridge, which is OAuth to Shorti's read-only MCP
  and off by default.

## Honest absence (house semantics)

A grader category that cannot be measured on a given input reports
`state: not_measured` with a reason — never a guessed score. A composer input
the schema cannot express is a validation error — never a silent drop. This
mirrors the upstream doctrine and is a feature, not a gap.

## Timeline format v0.1 (sketch — Agent A owns finalization)

```json
{
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
      "cue": "cold open on the reveal, no logo"
    }
  ],
  "subtitles": {"mode": "none"},
  "provenance": {"packet": "shorti-packet-<slug>.md"}
}
```

Rules: `beats[].t` are absolute seconds, non-overlapping, sorted. `role` is one
of `hook | development | payoff | cta | other`. Everything optional except
`version`, `canvas`, `beats`, and per-beat `t` + `shot`.

## Module interfaces (frozen for v0 — code to these names)

```python
# src/viralint/timeline/__init__.py          (Agent A)
load(path: str | Path) -> Timeline            # validates; raises TimelineError
validate(obj: dict) -> list[str]               # [] when valid

# src/viralint/compose/__init__.py            (Agent A)
render(timeline: Timeline, out: str | Path, *, dry_run: bool = False) -> Path
# ffmpeg/ffprobe via subprocess only; raise ComposeError with the ffmpeg stderr tail

# src/viralint/grade/__init__.py              (Agent B)
grade_video(path: str | Path) -> Scorecard
grade_timeline(t: Timeline | dict) -> Scorecard
# Scorecard: .categories -> list[CategoryResult(name, state, measured, band, verdict, why)]
#   state: "measured" | "not_measured"; verdict: "in_band" | "out_of_band" | None
# .render_markdown() -> str ; .render_terminal() -> str
# No single overall score — the card IS the result.

# cli.py                                       (Agent A wires; B's functions behind it)
viralint validate <timeline.json>
viralint compose <timeline.json> -o out.mp4 [--dry-run]
viralint grade <file.mp4 | timeline.json> [--json | --markdown]
```

## Grader v0 categories (Agent B owns; measured with ffmpeg/ffprobe only)

| category | video mode | timeline mode |
|---|---|---|
| `hook_window` | time of first cut / first high-motion moment (scdet) | first beat with role=hook: onset + length |
| `cut_cadence` | cuts per 10s via scdet, band per duration class | beats per 10s |
| `duration_fit` | container duration vs band | last beat end vs band |
| `structure_completeness` | not_measured (honest absence) | hook/development/payoff roles present |
| `text_density` | not_measured in v0 | chars-on-screen seconds ratio |

Bands live in `rules/structure.yaml` with fields: `category`, `band`,
`provenance: provisional`, `why` (one plain-English sentence). No other rule
metadata in v0.

## Ownership map (parallel build — do not cross)

- **Agent A**: `src/viralint/timeline/`, `src/viralint/compose/`, `cli.py`,
  `test/test_timeline.py`, `test/test_compose.py`
- **Agent B**: `src/viralint/grade/` (incl. `rules/`), `test/test_grade.py`
- **Agent C**: `SKILL.md`, `README.md`, `README-ko.md`, `README-zh.md`,
  `examples/` (2 sample timelines + 1 example scorecard markdown)
- Orchestrator only: `pyproject.toml`, `DESIGN.md`, `LICENSE`, `.gitignore`,
  `src/viralint/__init__.py`, `providers/`, `shorti/` (both empty stubs in v0),
  all git operations. **Builders never run git.**

## Engineering policy

- Python ≥ 3.11. Dependencies: stdlib + `pyyaml` + `jsonschema` only.
  ffmpeg/ffprobe are external binaries invoked via subprocess.
- Tests: pytest. Test media is generated on the fly with ffmpeg `lavfi`
  (`testsrc`, `color`, `sine`) — no binary assets committed, skip cleanly with
  a message when ffmpeg is absent.
- Code, comments, and errors in English. Terse, typed, no framework ceremony.
- Every subprocess call captures stderr and surfaces its tail on failure.
