# Local workspace coverage (2026-09-28)

This note records what was reviewed in the local Maze Crawler workspace and
why the public repository is smaller than the workspace. It is an accounting
note, not a request to redistribute competition files.

## Reviewed inventory

At review time the local workspace contained approximately 4.2 GiB across
1,863 files. The public archive contains the first-party source and selected
derived evaluation receipts; it intentionally does not mirror the local
workspace byte-for-byte.

| Local area | Review result | Public treatment |
| --- | --- | --- |
| `scripts/`, `baselines/`, reviewed submission source | Code and experiment helpers | Release only after authorship/provenance review; reviewed first-party variants are already under `experiments/` and `submissions/`. |
| `docs/` | Mixed research notes, competition pages, and operator prompts | Research notes may be adapted; pages are represented by official URLs; operator prompts are not copied when they contain machine paths or secret-like material. |
| `data/` | Competition inputs and downloaded leaderboard/replay material | Pointer-only. Keep the official competition URL, retrieval time, version, and a local hash; do not redistribute the source files. |
| `external/` | Copied public notebooks and competitor kernels | Attribution/index only. Upstream authors and licenses remain authoritative. |
| `reports/` | Mixed derived scores, raw replays, leaderboard exports, and diagnostics | Publish compact, derived receipts only. Raw rows and replay payloads stay local unless a separate license review clears them. |
| virtual environments and caches | Machine-local dependencies | Never publish. Recreate from documented dependencies. |

The public release therefore preserves the research path without claiming that
the competition platform's inputs or other participants' artifacts are ours to
redistribute. The official source is the [Maze Crawler competition page](https://www.kaggle.com/competitions/maze-crawler).

## What remains local

The local workspace still contains the excluded source files and large caches.
Nothing was deleted as part of this review. Before any cleanup, generate a
fresh manifest containing relative path, byte count, and SHA-256, then verify a
separate artifact host or Kaggle Dataset by download and hash readback.

## Reproduction boundary

To reproduce an experiment, obtain the competition inputs from Kaggle after
accepting its rules, place them in a local ignored directory, and run the
first-party source from this repository. A score or replay observed locally is
not an official leaderboard claim unless the corresponding Kaggle record is
linked and independently verifiable.
