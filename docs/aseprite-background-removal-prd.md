# PRD: AI Background Removal for Animated Aseprite Sprites

## Overview

This project will provide a local workflow for removing backgrounds from animated `.aseprite` sprite files. The initial target input is an animated sprite created from extracted video frames, where each frame may contain a white, near-solid, or natural/video background. The output should be a new animated `.aseprite` file with transparent backgrounds while preserving animation timing and sprite structure.

The first version should be CPU-first and run on a typical laptop without an Nvidia GPU.

## Problem

Animated sprites extracted from video often include unwanted backgrounds. Removing those backgrounds manually frame by frame is slow and inconsistent. Existing AI background-removal tools are usually designed for single images or videos, not native `.aseprite` files. When applied frame by frame, AI masks can flicker between animation frames, causing unstable sprite edges.

The product needs to make this workflow practical for pixel-art and animation use cases, not just produce isolated transparent PNGs.

## Goals

- Remove backgrounds from animated `.aseprite` files.
- Preserve frame order, frame duration, canvas size, and animation tags where possible.
- Run locally on CPU without requiring CUDA or an Nvidia GPU.
- Support unknown backgrounds, including white, near-solid, and video-like backgrounds.
- Minimize frame-to-frame mask jitter.
- Produce a new `.aseprite` output file and optional frame preview exports.
- Keep the first implementation small enough to validate model quality and performance before building a UI.

## Non-Goals

- Building a full image editor.
- Training a custom AI model in the first version.
- Requiring cloud inference.
- Requiring Nvidia CUDA.
- Supporting every possible `.aseprite` feature in the first milestone.
- Replacing Aseprite's native editing tools.
- Shipping a public web service in the first milestone.

## Users

Primary user:

- A creator or developer working with animated sprites generated from video frames who wants a fast local way to remove backgrounds before editing or using the sprite in a game.

Secondary users:

- Pixel artists cleaning up rotoscoped or AI/video-derived animation.
- Game developers preparing character sprites from footage.
- Tool builders who need a repeatable batch process for sprite cleanup.

## Input And Output

### Input

- `.aseprite` file containing one or more animation frames.
- Frames may have one or more layers.
- Background may be white, near-solid, green-screen-like, or natural/video-derived.

### Output

- New `.aseprite` file with transparent background.
- Optional PNG frame sequence for inspection.
- Optional mask frame sequence for debugging.
- Optional processing report with timing, model used, and warnings.

## Recommended Technical Direction

Use a CLI-first pipeline:

1. Decode or export `.aseprite` frames.
2. Flatten each frame to an RGB/RGBA image for background-removal inference.
3. Run AI background removal using a CPU-capable model.
4. Post-process alpha masks for sprite consistency.
5. Rebuild a `.aseprite` file with the processed frames.
6. Preserve animation metadata where feasible.

The initial implementation should not be based directly on `bgbye`. `bgbye` is useful as a reference for comparing open-source models, but its architecture is a React/FastAPI web app with a CUDA-oriented backend. Its video flow extracts frames, removes backgrounds independently, and re-encodes a transparent WebM. That does not solve `.aseprite` preservation or temporal mask consistency.

## Model Strategy

Start with `rembg[cpu]` because it supports local CPU inference through ONNX Runtime and includes multiple models.

Initial model candidates:

- `isnet-anime`: likely useful for stylized or anime-like sprites.
- `birefnet-general-lite`: likely useful for general video-derived sprites with better quality than older lightweight models.
- `birefnet-general`, `birefnet-portrait`, `birefnet-dis`, `birefnet-hrsod`, `birefnet-cod`, and `birefnet-massive`: stronger BiRefNet candidates available through `rembg[cpu]`; benchmark selectively because CPU runtime and model size may be high.
- `bria-rmbg`: a strong background-removal candidate available through `rembg[cpu]`; check the upstream model license before commercial use.
- `u2net`: general U2Net baseline and direct `bgbye` overlap.
- `u2net_human_seg`: human-segmentation candidate and direct `bgbye` overlap.
- `silueta`: lightweight fallback for speed.
- `u2netp`: lightweight fallback for speed and compatibility.
- `isnet-general-use`: useful general-purpose quality baseline.

Avoid using BRIA RMBG as the default because its model license may require additional review before commercial use.

Consider ORMBG later because it is Apache-2.0, but it is optimized for humans and may not generalize to all sprite subjects.

## Background Removal Strategy

The product should combine AI masking with optional deterministic cleanup:

- Run one reused model session across all frames.
- Generate an alpha mask per frame.
- Apply thresholding to remove low-confidence background remnants.
- Apply morphological cleanup to remove small isolated artifacts.
- Optionally keep the largest foreground component.
- Optionally feather or soften alpha edges.
- Compare neighboring masks to detect sudden changes.
- For near-solid backgrounds, optionally combine AI masks with color-key detection.

Temporal consistency is a core risk. The first version should expose enough debug output to compare raw model masks and cleaned masks.

## Functional Requirements

### Milestone 1: CLI Prototype

- Accept an input `.aseprite` path.
- Accept an output `.aseprite` path.
- Select a background-removal model.
- Process all animation frames.
- Preserve frame count and frame order.
- Preserve frame duration where supported by the chosen `.aseprite` read/write approach.
- Export optional processed PNG frames.
- Export optional mask PNG frames.
- Print progress and processing time.

### Milestone 2: Quality Controls

- Add alpha threshold configuration.
- Add mask cleanup configuration.
- Add optional color-key assisted removal.
- Add optional crop/padding settings if needed by model inference.
- Add preview contact sheet export.
- Add warnings for likely flicker or unstable masks.

### Milestone 3: Aseprite Metadata Preservation

- Preserve animation tags.
- Preserve slices if feasible.
- Preserve layer names or create a clear processed layer.
- Decide how to handle multiple layers:
  - flatten all visible layers into one processed layer, or
  - process only selected layers, or
  - process composited output and write a clean result layer.

### Milestone 4: UI

- Build a local desktop or web UI only after the CLI quality is acceptable.
- Provide model selection, preview, and export controls.
- Allow side-by-side inspection of original, mask, and result frames.

## Non-Functional Requirements

- Must run without Nvidia CUDA.
- Must be usable offline after models are downloaded.
- Must avoid destructive edits to the original `.aseprite` file.
- Should process small sprites interactively enough for iteration.
- Should cache downloaded model files.
- Should provide deterministic outputs for the same inputs and settings.
- Should fail clearly when a model or `.aseprite` feature is unsupported.

## Performance Expectations

Initial acceptable target:

- Small test animation under 100 frames should complete on CPU without exhausting memory.
- Processing may take seconds to minutes depending on model and frame size.
- Model sessions should be reused to avoid reloading per frame.

Performance should be measured before adding parallelism. Parallel frame processing may increase memory use and should not be default on low-end laptops.

## Risks

- AI masks may flicker between frames.
- CPU inference may be slow for large frame counts or high-resolution frames.
- `.aseprite` read/write support may not preserve all metadata.
- Some subjects may be poorly segmented by general-purpose models.
- White or bright clothing/props may be mistaken for background when color-key assistance is enabled.
- Fine sprite details may be lost by aggressive mask cleanup.

## Open Questions

- Should the output preserve original layer structure or write a flattened processed animation?
- Should the first tool depend on the Aseprite CLI, a Python parser/writer, or both?
- What sprite dimensions and frame counts are typical for the target workflow?
- Are subjects usually humans, anime-style characters, game objects, or mixed content?
- Is commercial use required for the model licenses?
- Should the tool support batch processing multiple `.aseprite` files?

## Success Criteria

The first useful version is successful when:

- It processes `images/sprite.aseprite` into a new `.aseprite` file.
- The output opens in Aseprite.
- Frame timing and frame count are preserved.
- Most background pixels are transparent.
- The foreground remains recognizable and usable.
- Mask flicker is low enough that the animation is worth manual cleanup instead of frame-by-frame manual masking.

## Validation Plan

Use the existing sample files:

- `images/sprite.aseprite` as the primary animation benchmark.
- `images/susan.png` as a single-image quality check.
- `images/talk.mp4` as a reference for future video-frame workflows.

For each candidate model, compare:

- visual quality
- edge stability across frames
- processing time
- memory usage
- failure cases

The first decision gate should be whether CPU-based `rembg` quality is good enough. If it is not, the next options are model-specific ONNX workflows, a cloud/GPU optional path, or a semi-automatic workflow with manual mask correction.
