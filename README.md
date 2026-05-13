# Aseprite Background Remover

CPU-first CLI for removing backgrounds from animated `.aseprite` sprites.

The project is currently in scaffold phase. See:

- [PRD](docs/aseprite-background-removal-prd.md)
- [CLI implementation plan](docs/cli-implementation-plan.md)
- [Development setup](docs/development.md)

## CLI Examples

After installing in editable mode, run:

```bash
background-remover --help
```

List supported models:

```bash
background-remover --list-models
```

The expanded model set is still CPU-first through `rembg[cpu]`. It includes
the original fast candidates plus stronger rembg models that overlap with the
models reviewed in `bgbye`, such as `bria-rmbg`, `u2net`, and
`u2net_human_seg`. Larger BiRefNet models may be slow on CPU, so benchmark a
small subset before processing a full animation.

Inspect an Aseprite file without processing:

```bash
background-remover inspect images/sprite.aseprite
```

Preview a full processing run without loading a model:

```bash
background-remover process images/sprite.aseprite output/sprite.processed.aseprite --dry-run
```

Run the Phase 2 still-image smoke test:

```bash
background-remover remove-image images/susan.png output/susan.png \
  --model isnet-anime \
  --mask-output output/susan.mask.png \
  --overwrite
```

Compare stronger CPU candidates on a still image:

```bash
background-remover benchmark-image images/susan.png output/model-benchmark \
  --models bria-rmbg birefnet-general-lite u2net u2net_human_seg isnet-anime \
  --overwrite
```

Process an animated sprite and export review artifacts:

```bash
background-remover process images/sprite.aseprite output/sprite.processed.aseprite \
  --mask-output-dir output/sprite-masks \
  --report-output output/sprite.report.json \
  --contact-sheet-output output/sprite.contact.png \
  --preview-output output/sprite.preview.gif \
  --overwrite
```

Full `process` example with every current flag:

```bash
background-remover process images/sprite.aseprite output/sprite.full.aseprite \
  --model isnet-anime \
  --frame-output-dir output/full/frames \
  --mask-output-dir output/full/combined-masks \
  --ai-mask-output-dir output/full/ai-masks \
  --color-key-mask-output-dir output/full/color-key-masks \
  --model-cache-dir .cache/rembg-models \
  --report-output output/full/report.json \
  --contact-sheet-output output/full/contact.png \
  --preview-output output/full/preview.gif \
  --area-jump-threshold 0.25 \
  --bbox-jump-threshold 32 \
  --overwrite \
  --verbose \
  --alpha-threshold 8 \
  --min-artifact-size 4 \
  --fill-hole-size 4 \
  --keep-largest-component \
  --feather-radius 0.5 \
  --color-key-sample-corners \
  --color-key-color "#ffffff" \
  --color-key-tolerance 24 \
  --color-key-protect-alpha 224
```

For a metadata-only preview of those settings, add `--dry-run`. To suppress
nonessential progress output, replace `--verbose` with `--quiet`. Use
`--no-cleanup` instead of the cleanup flags when you want raw model alpha.

Downloaded model files are stored in `.cache/rembg-models` by default.
Use `--model-cache-dir` on processing commands to choose a different cache.
