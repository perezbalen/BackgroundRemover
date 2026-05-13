# Metadata And Layer Policy

The current CLI writes a flattened processed output file. This is intentional
for the first usable pipeline: every processed frame is rebuilt as a single
normal RGBA layer named `Flattened`.

## Preserved

- Canvas width and height.
- Frame count.
- Frame order.
- Per-frame durations.
- Animation tags parsed by the current reader/writer.

## Not Preserved Yet

- Original layer names, hierarchy, visibility, opacity, blend modes, and cel
  structure. These are flattened into one processed output layer.
- Slices.
- Tilesets and tilemap cels.
- Palette and indexed/grayscale color-mode details. The current path supports
  32-bit RGBA sprites.
- User data and other Aseprite chunks not handled by the narrow reader/writer.

The CLI prints a flattening warning during `process`, and JSON reports include
the layer and metadata policy so downstream automation can detect the output
shape without opening the generated `.aseprite` file.
