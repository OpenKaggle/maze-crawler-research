# Release manifest

## Scope

This release contains 156 first-party CSV receipts copied from the local Maze
Crawler research workspace after a path-level audit. It includes files whose
names match one of these groups:

- `eval_*.csv`
- `*strategy*.csv`
- `*metrics*.csv`
- `*summary*.csv`
- `*failures*.csv`

The audit excludes every path under `replays/`, `replays_*/`, and
`top_competitors/`, as well as every file named `*episode*.csv`.

## Boundary

The CSVs are project-produced evaluation receipts. They retain useful
experiment detail such as candidate labels, seeds, outcomes, rewards, and
aggregate strategy metrics. They do not include original competition inputs,
server replay payloads, submission archives, model artifacts, or third-party
source copies.

The audit found no literal credentials and no machine-specific absolute paths
in this release set. The canonical file list and SHA-256 values are in
`MANIFEST.sha256`.

## Verification

From this directory, run:

```sh
shasum -a 256 -c MANIFEST.sha256
```
