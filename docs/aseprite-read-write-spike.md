# Aseprite Read/Write Spike

Phase 1 uses a small native Python parser/writer instead of the Aseprite desktop CLI.

## Decision

The first implementation uses a Python `.aseprite` parser/writer. This keeps the CLI usable on machines without Aseprite installed and gives the app direct access to frame buffers for CPU background-removal inference.

The writer intentionally produces a flattened RGBA `.aseprite` file with one visible layer. This is sufficient for the first background-removal pipeline, where each processed output frame is already a composited RGBA image.

## Supported In Phase 1

- RGBA sprites, 32 bits per pixel.
- Normal image layers.
- Visible layer compositing.
- Raw and zlib-compressed image cels.
- Linked cels.
- Frame durations.
- Animation tags.
- No-op flattened rebuild.

## Not Supported In Phase 1

- Indexed or grayscale sprites.
- Tilemap cels.
- Non-normal blend modes.
- Full original layer preservation.
- Slices.
- User data.
- Palette editing.
- Aseprite CLI fallback.

## Sample Inspection

Use:

```bash
PYTHONPATH=src python3 -m background_remover.cli inspect images/sprite.aseprite
```

Current sample result:

- Canvas: `720x720`
- Color depth: `32 bpp`
- Frames: `10`
- Frame durations: `83 ms` for each frame
- Layers: `1`, named `Layer 1`
- Tags: `Talk`, frames `0-9`

Use the no-op rebuild:

```bash
PYTHONPATH=src python3 -m background_remover.cli rebuild-noop images/sprite.aseprite output/sprite.rebuilt.aseprite
```

The rebuilt file is expected to preserve canvas size, frame count, frame durations, and tags, but not original layer structure.

The rebuilt sample parses successfully through the native reader and produces identical flattened RGBA buffers compared to the original sample. Manual verification in the Aseprite desktop app is still pending because the Aseprite CLI/app is not installed in the current environment.
