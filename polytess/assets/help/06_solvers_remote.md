# Solvers, SSH & remote execution

## Solver profiles

**Settings → Solvers** defines how the MKS (Simpack) and FEM (Abaqus)
solvers are called: the command, whether it runs locally or via SSH on
a remote host, the remote login shell (tcsh, bash — or cmd for Windows
remotes) and a path mapping between your local view of the shared
storage and the remote one (`P:\projects ↔ /proj/projects`).

Solver blocks with an empty command field use these profiles — so the
same flow computes Windows→Windows, Windows→Linux or Linux→Linux
without editing the flow. The **Run Solver** block gives you direct
access with arguments, timeout and captured output.

## Command server

**Settings → Command Server** routes generic console commands (Run
Command, …) through one SSH host — useful when the studio runs on
Windows but the tools live on a Linux server. Requires key-based SSH.

## HPC

The HPC blocks (submit/query/cancel jobs, run job pool) manage batch
jobs including slot limits, resume and per-job signals. Run the same
flow headless on the server with the CLI — see *CLI & server*.
