# Example scorecard

> **Illustrative output — hand-written for documentation.** This page was not
> captured from a run. The band values below are placeholders that show the
> *shape* of a scorecard; the real bands live in
> `src/viralprinter/grade/rules/structure.yaml` and are marked
> `provenance: provisional`. Do not cite these numbers as thresholds.

What a grade looks like on the mp4 composed from
[`hook-payoff-916.json`](hook-payoff-916.json):

```
$ viralprinter compose examples/hook-payoff-916.json -o out.mp4
$ viralprinter grade out.mp4 --markdown
```

## out.mp4 — 9:16, 14.0s

| category | state | measured | band | verdict | why |
|---|---|---|---|---|---|
| `hook_window` | measured | first cut at 1.4s | ≤ 2.0s | in_band | Clips that held attention cut early; a late first cut asks for patience the feed does not give. |
| `cut_cadence` | measured | 1.4 cuts / 10s | 1.5 – 6.0 cuts / 10s | out_of_band | Cadence under the band reads as one long take, which works only when the take itself is the payoff. |
| `duration_fit` | measured | 14.0s | 7 – 35s | in_band | Very short clips leave no room for a payoff; long ones lose the loop. |
| `structure_completeness` | not_measured | — | — | — | Beat roles are not recoverable from pixels. Grade the timeline instead to measure this category. |
| `text_density` | not_measured | — | — | — | No OCR in v0, so on-screen text seconds cannot be read back from a rendered file. |

**There is no overall score. The card is the result.** Nothing here averages
into a grade, and `out_of_band` is a question to answer, not a defect: this
timeline holds one long development beat on purpose, and the honest reading is
"you are betting the middle on a single take."

## Recovering the not_measured rows

Both blanks are limits of the *input*, not of the grader. The same file graded
as a timeline — before a frame is rendered — can see its own roles and text:

```
$ viralprinter grade examples/hook-payoff-916.json --markdown
```

| category | state | measured | band | verdict | why |
|---|---|---|---|---|---|
| `structure_completeness` | measured | hook + development + payoff present | all three present | in_band | The three-beat spine recurred across analyzed clips; a missing payoff is the most common structural hole. |
| `text_density` | measured | 15.6 chars/s on screen | 5 – 40 chars/s | in_band | Text competing with the shot costs more attention than it buys. |

A category that cannot be measured says so and says why. It never guesses a
score — see the honest-absence section of the [README](../README.md).

*(Again: illustrative. Run the commands on your own file for real output.)*
