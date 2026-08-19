# Show HN draft (founder posts from their own account)

**Title (80 chars max):**

> Show HN: ViralPrinter – open-source composer and structure linter for shorts

**Body:**

We built an MIT-licensed tool that does two things for short-form video:

- **Compose**: write a short as a declarative JSON timeline (beats, shots, text,
  music) and render it to mp4 with ffmpeg. Local, no accounts.
- **Grade**: run any short — including the raw output of any AI video
  generator — against viral-structure rules: hook window, cut cadence,
  duration fit. There is deliberately no overall score; the card is the result,
  and categories that can't be measured say `not_measured` with the reason
  instead of guessing.

It is agent-skill-first: paste one line into Claude Code, Cursor, or any agent
CLI that reads skills, and the agent drives the whole loop —

    Use this skill: https://raw.githubusercontent.com/ds4psb-ai/viralprinter/main/SKILL.md — grade this short: ./out.mp4

To test the grader we pointed it at the demo reel of the most popular
open-source video generator on GitHub (110k stars). The finding surprised us:
in 15 of its 16 demo clips, every detected cut lands on a fixed whole-second
grid — 2s, 3s, 4s, or 5s intervals, frame-exact at 30fps — and no clip cuts
before 2.0 seconds. The cuts are on a clock, not on the content. Full method,
every JSON receipt, and the limits of our own instrument (scdet is a proxy;
two first-cut figures are upper bounds) are in the repo:
`docs/launch/grading-the-number-one-repo.md`.

The rules v0 are hand-set coarse bands marked `provenance: provisional` — they
encode which axes are worth measuring, not measured truth. A regeneration from
a corpus of analyzed breakout shorts is the roadmap, along with BYO-key
provider adapters (client-side only; we never hold keys).

Repo: https://github.com/ds4psb-ai/viralprinter
`pip install viralprinter` · `npx skills add ds4psb-ai/viralprinter`

---

*Posting notes (not part of the HN body): post between 14:00–17:00 UTC on a
weekday for best first-hour exposure; first comment should disclose the Shorti
connection plainly ("we build a commercial evidence layer; the composer,
grader, and skill are MIT and run without it") — HN rewards the disclosure and
punishes its absence.*
