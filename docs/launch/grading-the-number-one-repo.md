# What a 110,000-star video generator actually prints

**Generators print videos. ViralPrinter prints structure.**

ViralPrinter is a composer and a structure linter for short-form video: write a short
as declarative JSON, render it to mp4 with ffmpeg, and grade any short — including the
raw output of a generator — against viral-structure rules. Measurement is ffmpeg and
ffprobe only, it runs on your machine, and nothing is uploaded.

You do not have to install it to try it. Paste this into Claude Code, Cursor, or any
agent CLI that reads skills:

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — grade this short: ./out.mp4
```

To find out what the grader actually says about generated video, we pointed it at the
best advertisement a generator has: its own demo reel.

## Why MoneyPrinterTurbo

[MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) generates a finished
short from a topic or a keyword. It had 109,647 stars and 16,649 forks when we checked
the GitHub API on 2026-08-19. Its demo gallery is a public, stable, downloadable set of
clips that its own authors chose to represent the tool at its best, which makes it the
fairest thing we could measure.

We picked it because we admire it. It solved distribution — a one-command path from an
idea to a rendered file, documented well enough that more than sixteen thousand people
forked it — and its skill-file playbook is the pattern we copied for our own. This is not
a takedown. It is the same tool we would run on your footage, run on theirs, with the
receipts committed next to it.

Nothing below is a prediction. There are no view counts here, no multipliers, no claim
that any clip will or will not travel. Every number is a structural measurement of a
file, and every one of them traces to a JSON receipt in
[`results/`](results/).

## Method

**The videos.** Both READMEs
([README.md](https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/README.md),
[README-en.md](https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/README-en.md),
fetched 2026-08-19, hashes in [`results/manifest.json`](results/manifest.json)) show a
demo gallery of 16 clips: 8 portrait, 8 landscape, 8 narrated in Chinese and 8 in
English. Each links to a viewer page at `harry0703.github.io/mpt-assets/?video=<name>.mp4`
and the file itself is served as a release asset, so we fetched each one with
`curl -L` from
`https://github.com/harry0703/mpt-assets/releases/download/assets/<name>.mp4`.

**Attempted 16, downloaded 16, graded 16.** No download refused, no file came back as
HTML, no grade failed. Every file's sha256 and download timestamp is in the manifest;
had any of them 403'd, that row would say so instead.

**The command**, once per file:

```
cd /path/to/viralprinter && PYTHONPATH=src .venv/bin/python cli.py grade <file>.mp4 --json
```

Grader: `viralprinter` 0.1.0 at commit `d525acc`, rules file
`src/viralprinter/grade/rules/structure.yaml`
(sha256 `7909395d…`), scene detection by ffmpeg's `scdet` filter at its own default
threshold of 10.0.

**The honesty rules**, which matter more than the numbers:

- **The bands are provisional.** Every band in v0 is a hand-set placeholder marked
  `provenance: provisional`. It encodes which axis is worth measuring and roughly where
  the edges sit — not a measured threshold. `out_of_band` is a question worth answering,
  not a defect, and no band here should be quoted as a finding on its own.
- **There is no overall score.** The card is the result. Averaging five categories would
  invent a precision the rules do not have, so ViralPrinter does not offer the number
  people would most like to screenshot.
- **`not_measured` is an answer.** A category that cannot be measured on a given input
  says so, with the reason, instead of guessing. Two of the five rows come back
  `not_measured` on every video in this study. They are printed, not hidden.

## Results

All 16 cards, sorted by duration. `cuts` and `cut grid` come from
[`results/cut-times.json`](results/cut-times.json); every other column is lifted
directly from that clip's card.

| clip | lang | duration | cuts | cuts/10s | first cut | cut grid | hook_window | cut_cadence | duration_fit |
|---|---|---:|---:|---:|---:|---|---|---|---|
| When the City Wakes | ZH | 13.60s | 6 | 4.41 | 2.0s | 2s | `in_band` | `in_band` | `in_band` |
| Spring Is Made for Travel | ZH | 14.03s | 22 | 15.68 | 3.0s | irregular | `out_of_band` | `out_of_band` | `in_band` |
| What Mountains Teach Us | EN | 17.70s | 5 | 2.83 | 3.0s | 3s | `out_of_band` | `out_of_band` | `in_band` |
| Small Habits, Lasting Change | EN | 19.13s | 9 | 4.71 | 2.0s | 2s | `in_band` | `in_band` | `in_band` |
| Making Space for Creative Work | EN | 19.90s | 4 | 2.01 | 4.0s | 4s | `out_of_band` | `out_of_band` | `in_band` |
| The Future of Everyday Robotics | EN | 20.73s | 6 | 2.89 | 3.0s | 3s | `out_of_band` | `in_band` | `in_band` |
| The Details of Pour-Over Coffee | ZH | 22.60s | 7 | 3.10 | 3.0s | 3s | `out_of_band` | `in_band` | `in_band` |
| The Science Inside Coffee | EN | 22.73s | 7 | 3.08 | 3.0s | 3s | `out_of_band` | `in_band` | `in_band` |
| Light in the Deep Ocean | ZH | 23.13s | 3 | 1.30 | 4.0s | 4s (1 missed) | `out_of_band` | `out_of_band` | `in_band` |
| How Reading Shapes Us | ZH | 23.23s | 4 | 1.72 | 5.0s | 5s | `out_of_band` | `out_of_band` | `in_band` |
| The Future of Clean Energy | ZH | 24.20s | 7 | 2.89 | 6.0s | 3s (1 missed) | `out_of_band` | `in_band` | `in_band` |
| Why Ocean Conservation Matters | EN | 24.63s | 4 | 1.62 | 8.0s | 4s (2 missed) | `out_of_band` | `out_of_band` | `in_band` |
| Designing More Sustainable Cities | EN | 26.60s | 6 | 2.26 | 4.0s | 4s | `out_of_band` | `out_of_band` | `in_band` |
| Why We Still Explore Space | ZH | 26.90s | 6 | 2.23 | 4.0s | 4s | `out_of_band` | `out_of_band` | `in_band` |
| A Seed's Journey | ZH | 43.60s | 10 | 2.29 | 4.0s | 4s | `out_of_band` | `in_band` | `in_band` |
| A Brief History of Human Flight | EN | 59.07s | 13 | 2.20 | 4.0s | 4s (1 missed) | `out_of_band` | `in_band` | `in_band` |

`cuts` counts scene-change events, which is not always the same as shots — see
`Spring Is Made for Travel` below. `cut grid` is the single interval every detected cut
in that clip is a multiple of, with any skipped multiples noted.

Tallies: `duration_fit` 16 of 16 `in_band`. `cut_cadence` 8 of 16 `in_band` — of the
eight outside, seven fall below their floor and one above its ceiling. `hook_window` 2
of 16 `in_band`. `structure_completeness` and `text_density` are `not_measured` on all
16, which is 32 of the study's 80 rows.

### One card in full

`The Science Inside Coffee`, printed by `cli.py grade … --markdown` exactly as the tool
emits it. It is the most typical card in the set: a length that fits, a cadence inside
its band, an opening that arrives after the window closed, and two honest blanks.

```markdown
# viralprinter scorecard

**source**: `15-en-portrait-coffee-science.mp4` — **mode**: video

| category | state | measured | band | verdict | why |
|---|---|---|---|---|---|
| `hook_window` | measured | 3.00s | onset <= 2s, length 0.5-3s | out_of_band | Short-form viewers commit or leave in the opening moments, so a hook that starts later than about two seconds, or runs long without resolving, has already spent the attention it was meant to buy. |
| `cut_cadence` | measured | 3.08/10s | 2.5-11/10s (medium clip) | in_band | A short holds attention by changing what is on screen, but a longer clip needs a calmer rhythm than a very short one, so the workable range of cuts per ten seconds narrows as the clip gets longer. |
| `duration_fit` | measured | 22.73s | 7-60s | in_band | Below roughly seven seconds there is no room to pay a hook off, and past about a minute a short-form clip stops being one thing a viewer watches whole. |
| `structure_completeness` | not_measured | - | requires hook, development, payoff | - | Beat roles are an authoring fact, not a pixel fact: nothing in an encoded video says which shot was meant as hook, development, or payoff. Grade the timeline to measure this. |
| `text_density` | not_measured | - | 3-45 chars | - | Reading on-screen text out of pixels needs OCR, which v0 does not ship. Grade the timeline instead, where the text is declared rather than inferred. |

Bands are provisional v0 placeholders, not measured thresholds. Rows marked `not_measured` are honest absences, not zeros.
```

## The honest read

**Length is solved.** All 16 clips land inside the duration band, from 13.60s to 59.07s.
That is not faint praise. Picking a length that fits the format is a real editorial
decision, and a generator that returns a 3-second stub or a 4-minute lecture would fail
here. This one does not, 16 times out of 16.

**The cuts are on a clock, not on the content.** This is the finding, and it is sharper
than we expected. In 15 of the 16 clips, *every* detected cut falls on a whole second.
Not near one — on it: 2.000, 4.000, 6.000. At 30fps that is frame 60, frame 120, frame
180, so this is not a rounding artifact of the measurement.

Go one step further and the clips resolve into single fixed intervals. Each of those 15
cuts on one constant: 2 seconds (2 clips), 3 seconds (5 clips), 4 seconds (7 clips), or
5 seconds (1 clip). In 11 of them the series has no gaps at all — every multiple of the
interval, start to finish. `A Brief History of Human Flight` cuts at 4, 8, 12, 16, 20,
24, 28, 32, 36, 40, 48, 52, 56. `The Details of Pour-Over Coffee` cuts at 3, 6, 9, 12,
15, 18, 21.

That is a segment-assembly rhythm: pick a shot length, lay stock footage end to end
under a narration track. It is a completely reasonable thing for a generator to do, and
it is why `cut_cadence` passes half the time — a 3-second grid puts you at 3.3 cuts per
10 seconds, which sits inside the band by construction.

**Nothing opens early.** No clip in the set has a detected cut before 2.0 seconds. The
two that scored `in_band` on `hook_window` did it by landing on exactly 2.000 — the band
edge, not inside it. The rest arrive at 3, 4, 5, 6, or 8 seconds. This follows directly
from the grid: if the interval is 4 seconds, the first cut is at 4 seconds, because a
constant does not know what the clip is about.

**The one exception proves it.** `Spring Is Made for Travel` is the only clip with an
irregular series and the only cadence above a ceiling, at 15.68 cuts per 10 seconds. Its
first three detections are grid-perfect at 3, 6, 9 — and then 19 more land between 9.067
and 12.000, spaced 4 to 5 frames apart. That is one transition effect scoring as many
scene changes, not 19 shot changes. The grader counts scene-change events and cannot
tell those apart, so we are reporting its number and its cause together.

**What that means a creator should change.** One thing, and it is not the footage. The
cut grid is a constant; the first cut is the one edit that decides whether an opening
exists. A hook cut goes where the sentence lands — where the claim finishes, where the
reveal arrives — and a fixed interval cannot put it there because it does not know where
that is. Moving the first beat boundary off the grid is a timeline edit, not a
re-render: change one number, re-grade, see the row flip. That loop — author, compose,
grade — is the whole reason this repo exists.

## What ViralPrinter could not see

Two of the five rows came back `not_measured` on all 16 clips, and we would rather print
that than fill it in.

**`structure_completeness`** asks whether the short has a hook, a development, and a
payoff. Beat roles are an authoring fact, not a pixel fact. Nothing in an encoded file
says which shot was *meant* as the payoff, and no amount of scene detection recovers an
intention. Grading a timeline fills this row; grading an mp4 never will.

**`text_density`** asks how much text is on screen over time. Reading it out of pixels
needs OCR, which v0 does not ship — and here that is not a hypothetical gap. ffprobe
finds no subtitle stream in any of the 16 files; every one is exactly one video stream
and one audio stream, recorded in [`cut-times.json`](results/cut-times.json). We pulled
a single frame from two of them by eye — one English portrait, one Chinese landscape —
and both show a burned-in narration caption sitting in the pixels. A human sees that
text instantly; the grader cannot read a character of it. So the row stays blank instead
of guessing.

Three more limits, all real:

- **`hook_window` in video mode times the first cut, not a hook.** It is a proxy. A clip
  could open on a held shot that earns its attention without cutting, and this grader
  would mark it late.
- **A missing cut may be a missed cut.** `scdet` fires on visual change, so two
  consecutive stock clips that look alike may produce no detection. Four clips show gaps
  in an otherwise perfect grid. For `The Future of Clean Energy` (6.0s) and
  `Why Ocean Conservation Matters` (8.0s), the gap is at the *start*, which means those
  two first-cut figures are upper bounds — the real first cut may be earlier, and we
  cannot tell from outside the file.
- **The bands are still guesses.** They are hand-set v0 placeholders. Rules v1 will
  regenerate them from a measured distillation pass and retire the `provisional` mark.
  Until then, read the `measured` column and treat the verdict as a prompt.

## The receipts

- [`results/manifest.json`](results/manifest.json) — every source URL, sha256, HTTP
  status, and UTC download timestamp; attempted/downloaded/graded counts; the empty
  failure lists.
- [`results/<clip>.json`](results/) — 16 cards, each wrapping the grader's verbatim
  `--json` output with the file's hash and the grader's commit.
- [`results/cut-times.json`](results/cut-times.json) — every cut time in every clip, the
  supplementary measurement behind the grid finding, with its own limits written next to
  it.

Run it on your own file and see what it says:

```
Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — grade this short: ./out.mp4
```

Thanks to [@harry0703](https://github.com/harry0703) and the MoneyPrinterTurbo
contributors, whose demo reel made this measurable and whose distribution playbook we
studied closely.
