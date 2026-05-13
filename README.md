# Aseprite Background Remover

CPU-first CLI for removing backgrounds from animated `.aseprite` sprites.

The project is currently in scaffold phase. See:

- [PRD](docs/aseprite-background-removal-prd.md)
- [CLI implementation plan](docs/cli-implementation-plan.md)
- [Development setup](docs/development.md)

## Smoke Test

After installing in editable mode, run:

```bash
background-remover --help
```

Run the Phase 2 still-image smoke test:

```bash
background-remover remove-image images/susan.png output/susan.png --model isnet-anime --mask-output output/susan.mask.png
```

Downloaded model files are stored in `.cache/rembg-models` by default.
