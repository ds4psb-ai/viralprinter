# ViralPrinter

English · [한국어](README-ko.md) · [简体中文](README-zh.md)

**Generators print videos. viralprinter prints structure.**

A composer and a structure linter for short-form video. Write a short as
declarative JSON, render it to mp4 with ffmpeg, and grade any short — including
the raw output of an AI video generator — against viral-structure rules.

Status: v0. Timeline format `0.1`, rules `provisional`. The interfaces in
[DESIGN.md](DESIGN.md) are frozen for v0; everything else can still move.

## What it does

**Grade any short.** `viralprinter grade` takes an mp4 or a timeline JSON and returns
a scorecard: hook window, cut cadence, duration fit, structure completeness, text
density. It does not care where the file came from — a phone, an editor, or a
generator that handed you fifteen seconds with no opinion about where the cut
should go. Measurement is ffmpeg and ffprobe only; nothing is uploaded.

**Compose a timeline to mp4.** `viralprinter compose` renders a declarative timeline
— beats, shots, text, audio — into a finished file. Local, deterministic, no
account, no keys. ffmpeg does the work; viralprinter decides what to hand it.

**Drive the whole loop from an agent.** [SKILL.md](SKILL.md) is the distribution
surface: one paste teaches Claude Code, Cursor, or any agent CLI to go from an
idea to a shooting packet, to a timeline, to a rendered file, to a scorecard.

There is no overall score, on purpose. The card *is* the result — each category
carries what was measured, the band it was compared against, and one plain
sentence saying why that band exists. Averaging them would invent a precision the
rules do not have.

## Quickstart

### With an agent (the intended path)

Paste one sentence into any agent CLI that reads skills:

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — make me a shooting packet for TOPIC
```

The agent then follows SKILL.md on its own: build the packet, author a timeline
from your clips, validate it, compose it, grade the result, and hand you back an
absolute path. Same pattern, other jobs:

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — grade this short: ./out.mp4
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — I liked this one: <link to a short>, make me one like it
```

`https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md` is the raw URL of this repo's `SKILL.md`.

### By hand

```
git clone https://github.com/ds4psb-ai/viralprinter && cd viralprinter
uv pip install -e .          # or: pip install -e .

viralprinter validate examples/hook-payoff-916.json
viralprinter compose  examples/hook-payoff-916.json -o out.mp4
viralprinter grade    out.mp4 --markdown
```

Python ≥ 3.11, with `ffmpeg` and `ffprobe` on `PATH`. The example timelines point
at `clips/*.mp4`; swap in your own footage before composing.

### Evidence packets (optional)

Grading and composing need nothing but this repo. The *evidence* half — trend
genealogy, borrow formulas, shot-by-shot kits from analyzed real clips — comes
from Shorti's read-only MCP door, and is opt-in:

```
claude mcp add --transport http shorti https://api.shorti.ai/mcp/public-read/mcp
```

Read-only by contract: it never posts, edits, deletes, spends, or receives your
media. Skip it entirely if you only want to grade or compose.

## The timeline format

A short as code. Beats are absolute seconds, sorted and non-overlapping; `role`
is one of `hook | development | payoff | cta | other`.

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

Required: `version`, `canvas`, `beats`, and per-beat `t` + `shot`. Everything
else is optional — omit what you do not know rather than filling it in. Full
examples: [`examples/`](examples/), including a
[worked scorecard](examples/example-scorecard.md).

## Honest absence

A grader category that cannot be measured on a given input reports
`state: not_measured` with a reason, never a guessed score. Beat roles are not
recoverable from pixels, so a rendered file legitimately leaves rows blank —
grade the timeline to fill them. A composer input the schema cannot express is a
validation error, never a silent drop.

This is a feature. A card with two honest blanks tells you more than five
confident numbers, two of which were invented.

## What ships here, and what does not

- `grade/rules/*.yaml` is the only artifact derived from a private corpus, and
  only as **coarse categories and bands**. v0 values are hand-set and marked
  `provenance: provisional`. No corpus rows, embeddings, measurement schemas,
  prompt text, or model names are in this repository, and none will be.
- The bands describe structure that recurred in analyzed clips. They are not
  performance predictions, and `out_of_band` is a question worth answering, not
  a defect.
- No server-side secrets, ever. Future provider adapters read keys from *your*
  environment, run client-side, and transmit them nowhere but the provider's own
  API.
- Everything runs offline except two opt-ins: explicit provider render calls, and
  the Shorti bridge.

## Roadmap

- **Provider adapters** (`providers/`) — bring-your-own-key generation, entirely
  client-side, so a timeline can source shots it does not have on disk.
- **Shorti bridge** (`shorti/`) — turn an evidence packet into a draft timeline
  directly, instead of the agent transcribing it by hand.
- **Rules v1** — regenerate the bands from a measured distillation pass and
  retire `provenance: provisional`.

## License

MIT. See [LICENSE](LICENSE).
