# Aseprite Background Remover

CPU-first CLI for removing backgrounds from animated `.aseprite` sprites.

The project is currently in scaffold phase. See:

- [PRD](docs/aseprite-background-removal-prd.md)
- [CLI implementation plan](docs/cli-implementation-plan.md)
- [Development setup](docs/development.md)

## Desktop GUI

The GUI is a local PySide6 desktop app:

```bash
background-remover-gui
```

Windows File Explorer drag/drop is the first supported desktop integration. For
that workflow, run the GUI with native Windows Python from PowerShell or Windows
Terminal, not from WSL. A WSL/WSLg Qt window can appear on the Windows desktop,
but it is still a Linux app and does not provide reliable file drag/drop
integration with Explorer.

From the repository folder on Windows:

```powershell
py -3.12 -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -e ".[dev,gui]"
.\.venv-win\Scripts\background-remover-gui.exe
```

You can also double-click `launch-gui-windows.bat` from File Explorer. The
script creates `.venv-win` if needed, installs the GUI dependencies if the app
launcher is missing, and starts the native Windows GUI.

With the native Windows launch path, you can:

- drag `.aseprite` or supported image files from File Explorer into the app;
- process locally and review the output preview;
- drag the processed output image or the `Drag <filename>` toolbar handle back
  into File Explorer;
- use **Save As** as the fallback export path on every platform.

WSL is still useful for CLI development and tests, but not for Windows Explorer
drag/drop validation.

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

The CLI default model is `bria-rmbg`; pass `--model` when you want a different
quality/performance tradeoff.

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
  --fill-hole-size 0 \
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

## Flag Reference

### General flags

- `--model MODEL`: chooses the `rembg` model. The default is `bria-rmbg`.
  Larger models can improve masks, but they can be much slower on CPU. Use
  `background-remover --list-models` to see valid names.
- `--model-cache-dir PATH`: stores downloaded model files in `PATH`. The
  default is `.cache/rembg-models`.
- `--overwrite`: allows replacing an existing output file.
- `--quiet`: suppresses nonessential progress output.
- `--verbose` or `-v`: prints additional diagnostics. Repeat it for more
  verbosity where supported.
- `--dry-run`: for `process`, prints input metadata and planned settings
  without loading the model or writing processed frames.

### Output and review flags

- `--frame-output-dir DIR`: writes each processed RGBA frame as a PNG. Use this
  when you want to inspect exactly what will be packed into the output sprite.
- `--mask-output-dir DIR`: writes the final alpha mask for each frame. If
  color-key assist is enabled, this is the combined mask.
- `--ai-mask-output-dir DIR`: writes the cleaned AI mask before color-key assist.
  Use this with `--mask-output-dir` to see what color-key changed.
- `--color-key-mask-output-dir DIR`: writes the deterministic color-key mask.
  This only produces files when color-key assist is enabled.
- `--report-output PATH`: writes JSON metrics for each frame, including mask
  area and bounding-box movement.
- `--contact-sheet-output PATH`: writes a PNG sheet with original, mask, and
  result columns for quick visual review.
- `--preview-output PATH`: writes an animated GIF preview of the processed
  frames.
- `--mask-output PATH`: for `remove-image`, writes the image alpha mask.

### Cleanup flags

Cleanup changes the model alpha mask after `rembg` runs. If the raw model output
looks better, use `--no-cleanup`.

- `--no-cleanup`: disables mask cleanup and uses the model output as-is. This is
  the best baseline when debugging artifacts.
- `--alpha-threshold N`: makes alpha values below `N` transparent and values at
  or above `N` opaque. `N` must be from `0` to `255`. For example,
  `--alpha-threshold 8` removes very faint mask noise while keeping most soft
  edges. Higher values like `32` or `64` cut more edge pixels and can remove
  halos, but they can also make silhouettes jagged or erase fine details.
- `--min-artifact-size N`: removes connected foreground islands smaller than
  `N` pixels. The default is `4`. Use small values like `2` to `8` to remove
  isolated specks. Larger values can delete small legitimate details such as
  fingers, props, hair tips, or thin outlines.
- `--fill-hole-size N`: fills enclosed transparent holes up to `N` pixels. The
  default is `0`, which disables filling. Use small values like `1` to `4` only
  when the model leaves pinholes inside the character. Avoid this if cleanup
  creates white or background-colored pixels, because filling can make uncertain
  background pixels visible.
- `--keep-largest-component`: keeps only the largest connected foreground
  component. Use it when the subject is one separate object and cleanup needs to
  remove detached blobs. Do not use it when the sprite has separate parts that
  should remain visible, such as a detached weapon, effects, shadows, or smear
  frames.
- `--feather-radius R`: applies Gaussian blur to the cleaned alpha mask. `R` is
  a radius in pixels. `0` disables feathering. Values like `0.5` or `1.0`
  soften hard edges; larger values can create halos and make pixel art look
  blurry.

### Color-key flags

Color-key assist is useful when the source sprite has a near-solid background,
especially white or off-white video backgrounds. It combines deterministic color
matching with the AI mask.

- `--color-key-sample-corners`: samples the background color from visible corner
  pixels in each frame. Use this when the corners are representative background.
- `--color-key-color COLOR`: uses an explicit background color instead of
  sampling. Accepts `#RRGGBB`, such as `#ffffff`, or comma-separated RGB, such as
  `255,255,255`.
- `--color-key-tolerance N`: controls how close a pixel color must be to the
  background color to count as background. The value is RGB distance. Start
  around `16` to `24` for near-white backgrounds. Raise it if background remains;
  lower it if foreground details are being erased.
- `--color-key-protect-alpha N`: prevents color-key removal for pixels whose AI
  alpha is at least `N`. The default is `224`. Lower values protect more pixels
  from color-key removal, which preserves foreground but may keep background
  fringe. Higher values let color-key remove more pixels, which can clean halos
  but may cut into the subject.

### Report warning flags

These flags do not change the output image. They only control warnings in the
JSON report.

- `--area-jump-threshold R`: warns when neighboring frame mask area changes by
  more than ratio `R`. The default is `0.25`, meaning a 25% change. Lower values
  catch smaller flicker but may warn on normal motion.
- `--bbox-jump-threshold N`: warns when neighboring mask bounding-box centers
  move by more than `N` pixels. The default is `32`. Lower values are stricter;
  higher values are more tolerant of fast motion.
