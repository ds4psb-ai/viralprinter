---
name: viralprinter
description: Structure-first short-form video. Turn a topic, a product, or a pasted short-form URL into an evidence-backed shooting packet; compose a declarative timeline into an mp4 with ffmpeg; and grade any short — including the output of any AI video generator — against viral-structure rules. The agent reasons and composes; evidence is supplied, never invented.
---

# viralprinter — compose and grade short-form video, with structure evidence

You are driving two halves.

- **Local, always available.** The `viralprinter` CLI in this repo: `validate`,
  `compose` (timeline JSON → mp4 via ffmpeg), and `grade` (score any short
  against viral-structure rules). No account, no keys, no upload.
- **Evidence, optional.** Shorti's read-only MCP door: analyzed real short-form
  clips, their lineage (what moved, what mutated, what died), and per-clip
  borrow formulas (keep / change / never_touch) with audience receipts.

Shorti is not a video generator and you must not present it as one. **You do the
reasoning and the composing. Shorti supplies evidence and abstains honestly when
evidence is thin — pass its abstentions through; never fill them in.**

If the user only wants a short graded, skip the evidence half entirely: Flow G.

## Setup

### The tool (required for compose and grade)

```
git clone https://github.com/ds4psb-ai/viralprinter && cd viralprinter
uv pip install -e .          # or: pip install -e .
```

Python ≥ 3.11. `ffmpeg` and `ffprobe` must be on `PATH` — compose and video-mode
grading shell out to them. Confirm with `viralprinter --help` before promising a
rendered file. If the command or the binaries are missing, say so and stop
rather than describing output you did not produce.

### Shorti evidence (optional)

```
claude mcp add --transport http shorti https://api.shorti.ai/mcp/public-read/mcp
```

Any MCP-capable agent client takes that URL the same way. The first call
triggers browser OAuth — tell the user to complete it, then retry once. This
skill never collects API keys, never asks the user to paste secrets into chat,
and never uploads the user's media: the mount is read-only by contract (it never
posts, edits, publishes, deletes, or spends). Grading and composing need no
Shorti account; evidence packets are the part that does.

## Operating rules

1. **One combined question, maximum.** If inputs are missing (topic vs product
   vs URL, target aspect, language), ask once, together. Never ask for
   confirmation between tool calls.
2. **Locale.** Pass `locale` matching the user's language (`en`, `ko`, `ja`) on
   every call that accepts it, and answer entirely in the user's language.
3. **Numbers.** `observed_metrics` in evidence results are factual counts from
   the corpus — cite them as proof. Grader numbers are measurements of the file
   in front of you — cite them as measurements. Never produce predictive
   numbers: no forecast view counts, no "N×" multipliers, no ROI percentages.
   Structure claims, not outcome promises.
4. **Honest absence.** Thin or abstaining evidence is the tool working
   correctly, and so is a grader category reporting `state: not_measured` with a
   reason. Report the abstention as-is; never guess a substitute or a score.
5. **Don't paste raw JSON.** Synthesize. The user reads prose, the packet file,
   and the scorecard — not payloads.
6. **Retry discipline.** One retry per failed call. If a parameter is rejected,
   re-read the tool description instead of guessing again.
7. **Never invent media.** A timeline may only reference files that exist on
   disk. If clips are missing, say which ones and stop at the packet.

## Flow A — "make me a short about TOPIC" / "이거로 쇼츠 만들어줘"

1. `search_trend_genealogy` with the topic. Time-bound asks pass
   `moved_within_days` (7 for "this week", 30 for "these days").
2. Pick the strongest match (state your pick and why in one sentence — do not
   ask unless genuinely ambiguous).
3. `get_trend_genealogy_card` **exactly once** on that match — this is the
   borrow formula: keep / change / never_touch, lineage, audience proof.
4. `get_clone_kit_capsule` for the selected clip — the shot-by-shot 콘티.
5. Compile the **packet** (below), then continue into Flow F if the user has
   footage or wants a render.

## Flow B — "make a short for MY PRODUCT"

1. `suggest_trends_for_product` — `product_description=` works without any
   registration; use the user's own words for the product.
2. Then Flow A steps 2–5. If the user has a Shorti account with registered
   products, `list_my_products` + `get_my_product_truth` sharpen the fit.

## Flow C — the user pasted a short-form URL

A pasted URL is never a search. Call `preview_pasted_url` FIRST, then continue
with Flow A steps 3–5 on what it resolves.

## Flow D — mid-shoot coaching

- Next cut: `get_next_shot_cue` — one cue per call, shoot, repeat.
- "How did I do?": `get_shot_coaching_rubric`, then **you** grade the clip the
  user shows you against that rubric. The rubric call carries no file or URL
  parameter by design — clip understanding is yours, on media you already see.
  Never send the user's footage anywhere. For a structural second opinion on a
  finished file, run Flow G alongside it.

## Flow E — "what's new this week?"

`get_lifecycle_briefing` once; `get_started` is the first-contact orientation
when the user asks what Shorti can do at all.

## The packet — your first deliverable

Write a local file `shorti-packet-<slug>.md` in the working directory:

```
# <working title>

## Formula (borrowed from <lineage ref>)
keep / change / never_touch — verbatim from the genealogy card, with receipts.

## Shotlist
Numbered shots from the clone kit: beat, duration, framing, action, audio cue.

## Per-shot cues
The cues you would give one at a time on set (Flow D order).

## Grading rubric
The rubric you will grade dailies against.

## Evidence
Lineage references and observed_metrics — facts only, no forecasts.
```

Finish that step with exactly one machine-readable line:

```
PACKET_FILE=<absolute path>
```

## Flow F — packet → timeline → mp4 (close the loop)

The packet is a plan; this turns it into a file. Do not start it without media.

1. **Locate the media.** Ask the user once for the clip directory, or use the
   provider outputs already on disk. Every `src` you write must resolve.
2. **Author the timeline yourself.** Translate the packet's shotlist into one
   JSON file — you write it, no tool generates it. Fields, and only these:

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

   `beats[].t` are absolute seconds, sorted, non-overlapping. `role` is one of
   `hook | development | payoff | cta | other`. Required: `version`, `canvas`,
   `beats`, and per-beat `t` + `shot`. Everything else is optional — omit what
   you do not know instead of inventing it. Carry the packet filename in
   `provenance`. Working examples: `examples/*.json`.
3. `viralprinter validate <timeline.json>` — fix every error in the timeline. Never
   work around a validation error; it is telling you the plan is unrenderable.
4. `viralprinter compose <timeline.json> -o out.mp4` — use `--dry-run` first if the
   render is long or the media is unfamiliar.
5. Report what you built in prose, then exactly one machine-readable line:

   ```
   VIDEO_FILE=<absolute path>
   ```
6. Offer the grade, or run it directly if the user asked for a finished short:
   `viralprinter grade out.mp4 --markdown`, then Flow G's reporting rules.

## Flow G — "grade this short" (no Shorti account needed)

Works on any file the user points at, including the raw output of any AI video
generator, and on a timeline JSON before a single frame is rendered.

1. `viralprinter grade <file.mp4 | timeline.json> --markdown` (`--json` when a
   machine consumes it).
2. Report the card. **There is no overall score — the card is the result.** Do
   not average it, do not invent a grade, do not rank the video.
3. Read `not_measured` rows out loud with their reason. A video cannot expose
   its own beat roles, so some categories are only measurable in timeline mode;
   that gap is the honest answer, not a failure.
4. Say what the bands are: coarse, distilled, `provenance: provisional`. They
   describe structure that recurred in analyzed clips. They do not promise
   performance, and an `out_of_band` row is a question to answer, not a defect.
5. Then be useful — name the one structural change with the largest effect and,
   if the user wants it applied, go to Flow F.

## Failure protocol

- OAuth not completed → one sentence telling the user to finish the browser
  flow, then retry once.
- A ref-taking tool called cold (missing `trend_ref` etc.) → you skipped a step;
  back up one call in the flow instead of retrying blind.
- Persistent transport errors → report the last error verbatim and stop.
- `viralprinter` or `ffmpeg` not found → report the missing binary and the install
  line. Never simulate a render.
- Compose failure → the error carries the ffmpeg stderr tail. Quote it, then fix
  the timeline. Do not hand-run ffmpeg to route around the composer.
- Validation errors → fix the timeline and re-validate. Never pass an invalid
  timeline to `compose`.
