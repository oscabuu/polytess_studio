# CLI & server use

The same flow runs in the studio and headless — ideal for batch runs,
nightly jobs and HPC servers.

## Commands

    polytess-cli run flow.flow.json [--var name=value …] [--workdir DIR]
    polytess-cli validate flow.flow.json
    polytess-cli doc flow.flow.json
    polytess-cli --version

(In a Python environment the same commands are
`python -m polytess.cli …`.)

`--var` overrides graph variables per run — the tool for parameter
studies driven by an outer script or scheduler.

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
