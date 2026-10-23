# CLI & server use

The same flow runs in the studio and headless — ideal for batch runs,
nightly jobs and HPC servers.

## Commands

    polytess-cli run flow.flow.json [--var name=value …] [--workdir DIR]
    polytess-cli validate flow.flow.json
    polytess-cli doc flow.flow.json
    polytess-cli inputs flow.flow.json [--template values.json]
    polytess-cli run flow.flow.json --vars-file values.json
    polytess-cli board main.flow.json [--run CARD | --all | --reset CARD|all] [--json]
    polytess-cli --version

(In a Python environment the same commands are
`python -m polytess.cli …`.)

`--var` overrides graph variables per run — the tool for parameter
studies driven by an outer script or scheduler.

`inputs` prints the Viewer form of a flow (what a non-expert user
fills in) and `--template` writes a preset file with the current
values; `run --vars-file` validates and applies such a preset before
the run. `board` shows a main process (sub-workflow nodes = cards) with
its card statuses, runs one card after its unfinished predecessors
(`--run`), everything in dependency order (`--all`) or forgets results
(`--reset`) — the same state file (`<flow>.board.json`) the Viewer
uses, so a run started headless shows up Done in the Viewer.

Exit codes of `run`: `0` success, `1` at least one node failed (also
inside a sub-workflow with *Fail If Sub-Workflow Fails*), `2` invalid
`--vars-file` values, `130` interrupted.

## Deployment

- **Desktop**: the polytess executable — unzip and run, no Python
  required. Your license (`license.lic`) may live next to the
  executable or in `~/.polytess/`.
- **Server**: the compiled server package (tar.xz) with the system
  Python — small, no GUI dependencies. Custom blocks travel as plain
  Python files in `custom_library/` next to the installation.

## Reproducibility

Random-field and DOE blocks take explicit seeds: the same seed produces
bit-identical results — across studio, CLI and machines.
