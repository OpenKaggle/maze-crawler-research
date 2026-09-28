# Derived evaluation receipts

This directory contains 156 first-party local evaluation receipts from the
Maze Crawler research workspace. They are compact CSV records produced by the
project's local evaluation and analysis workflow: paired comparisons, strategy
metrics, summaries, and failure analysis.

The selection intentionally excludes replay JSON, downloaded server-event
payloads, `top_competitors/`, and CSVs named `*episode*`. A filename containing
`replay_summary` or `replay_failures` is retained only when it is a derived
summary table, not the underlying replay. No board state, action stream,
competition input, generated submission, copied kernel, or credential is part
of this release.

Candidate and opponent labels are retained as experiment provenance; they do
not redistribute another participant's implementation. These are historical
local research receipts, not claims about a current leaderboard position.

`MANIFEST.sha256` records every released CSV and its SHA-256 digest. To
reproduce a new evaluation, use the repository scripts with an authorized
competition environment and acquire all competition materials from their
official source.
