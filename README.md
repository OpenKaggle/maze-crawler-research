# Maze Crawler

Local workspace for the Kaggle `maze-crawler` competition.

This repository is the sanitized public research archive. It keeps first-party
experiment variants, evaluated submission source, evaluation helpers, and
written findings while excluding raw competition inputs, downloaded replay
corpora, virtual environments, and cached third-party baselines. The root
baseline was originally derived from the public Kaggle notebook credited in
`docs/research.md`; subsequent variants and analysis are preserved here with
that provenance visible.

## Publication status

This repository is public for research inspection and reproducibility. It is a
sanitized research archive, not yet a uniformly licensed software package.
The baseline provenance above is why no blanket open-source license is asserted
over files whose authorship or upstream license has not been verified.

## Setup

Create a local virtual environment and install the Kaggle CLI plus the
dependencies needed by the script you plan to run. The original `.venv` is
intentionally excluded from this archive.

```bash
.venv/bin/python -m pip install kaggle
kaggle competitions list --search maze-crawler
```

## Current Baseline

`main.py` is the current submission entry point. It now matches the stable `v24` / `v30` line, which is still the best online performer in this workspace.

- Stable mainline: `main.py` == `experiments/v24_jump_enemy_factory_avoid/main.py`
- Best recent online slot: `v30 stable v24 mainline deployment` with public score `1123.0`
- Best alternate online slot: `v31 alternative v19 delay24 scout deployment` with public score `985.4`
- Current experimental late-game patch: `experiments/v33_targeted_late_patch/main.py` (kept as a research branch, not promoted)

See `docs/research.md` for rule notes, leaderboard snapshot, local evaluation, and improvement plan.

The historical scores above are workspace records, not claims about the current
competition leaderboard.

## First-party submission source

`submissions/` preserves five reviewed, user-authored competition entry scripts
(`v51`, `v67`, `v71`, `v73`, and `v101`). They are source releases, rather than
organizer inputs or server-downloaded replay records. The corresponding
evaluation method is documented in this repository; original competition inputs
remain available only from the official competition page.

For large eligible artifacts—such as generated submission bundles or local
simulation evidence—this source repository links to a separate, hash-manifested
artifact release rather than placing large binary/replay data in Git history.
See [evaluation terms and version lineage](docs/EVALUATION_TERMS.md) for the
distinction between local paired evaluation, self-play, hosted-submission
observation, and official platform records.

## Evaluate Locally

```bash
.venv/bin/python -m py_compile main.py
.venv/bin/python scripts/evaluate_agents.py --agents main.py --opponent random --seeds 5
```

## Submit

```bash
.venv/bin/kaggle competitions submit maze-crawler \
  -f main.py \
  -m "v1 public top2 jump bfs baseline"
```

If Kaggle API has transient SSL failures, use:

```bash
scripts/submit_with_retry.sh
```

Eligible sanitized artifacts are also mirrored to the public
[Kaggle archive](https://www.kaggle.com/datasets/jahyee/maze-crawler-research-archive).
