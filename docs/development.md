# Development Setup

This project targets a CPU-first local workflow. Phase 0 intentionally avoids heavy AI dependencies; model packages will be added in later phases.

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

## Generated Files

Generated frames, masks, reports, model caches, and processed sprite outputs should stay out of source control. See `.gitignore` for the current ignored paths.
