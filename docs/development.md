# Development Setup

This project targets a CPU-first local workflow. The CLI installs the CPU
background-removal stack by default. Desktop GUI dependencies are optional so
headless CLI and test environments do not need Qt.

## Local Environment

Install Ubuntu's venv support if it is missing:

```bash
sudo apt-get install -y python3.12-venv
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the CLI in editable mode with development tools:

```bash
python3 -m pip install -e ".[dev]"
```

This installs the CPU background-removal stack. The first model run may download model files.

Run the CLI smoke test:

```bash
background-remover --help
```

Without installing, the CLI can also be checked from the repository root:

```bash
PYTHONPATH=src python3 -m background_remover.cli --help
```

Do not create the virtual environment with `sudo`. The `.venv` directory should be owned by your normal user so later dependency installs do not create root-owned project files.

## GUI Setup

Phase 0 establishes the GUI command and technical direction. The first supported
drag-out save target is Windows File Explorer. Linux file managers and macOS
Finder remain validation targets after the Windows path works, with Save As kept
as the reliable fallback on every platform.

The selected GUI toolkit is `PySide6`. The first delivery target is a
developer-run Python app installed from this repository; packaged executables
are deferred to the release phase.

Install the GUI extras into the same virtual environment:

```bash
python3 -m pip install -e ".[dev,gui]"
```

Launch the GUI:

```bash
background-remover-gui
```

For Windows File Explorer drag/drop, run the GUI with native Windows Python from
PowerShell or Windows Terminal, not from WSL. A WSL/WSLg Qt window can display
on Windows, but it is still a Linux app and does not provide reliable file
drag/drop integration with Explorer.

Example native Windows setup from the repository folder:

```powershell
py -3.12 -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -e ".[dev,gui]"
.\.venv-win\Scripts\background-remover-gui.exe
```

Without installing the console script, the entry point can be checked from the
repository root:

```bash
PYTHONPATH=src python3 -m background_remover.gui --help
```

## Generated Files

Generated frames, masks, reports, model caches, and processed sprite outputs should stay out of source control. See `.gitignore` for the current ignored paths.
