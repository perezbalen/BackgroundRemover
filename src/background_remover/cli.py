"""Command-line entry point for the Aseprite background remover."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from background_remover import __version__
from background_remover.aseprite import (
    AsepriteError,
    flatten_frames,
    read_aseprite,
    write_flattened_aseprite,
)
from background_remover.background import SUPPORTED_MODELS, BackgroundRemovalError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="background-remover",
        description="Remove backgrounds from animated Aseprite sprites.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect input sprite metadata.",
    )
    inspect_parser.add_argument("input", help="Path to an input .aseprite file.")

    rebuild_parser = subparsers.add_parser(
        "rebuild-noop",
        help="Flatten and rebuild an .aseprite file without background removal.",
    )
    rebuild_parser.add_argument("input", help="Path to an input .aseprite file.")
    rebuild_parser.add_argument("output", help="Path for the rebuilt .aseprite file.")

    process_parser = subparsers.add_parser(
        "process",
        help="Remove a sprite background. Implemented in a later phase.",
    )
    process_parser.add_argument("input", help="Path to an input .aseprite file.")
    process_parser.add_argument("output", help="Path for the processed .aseprite file.")
    process_parser.add_argument(
        "--model",
        default="isnet-anime",
        help="Background-removal model to use once model support is implemented.",
    )

    remove_image_parser = subparsers.add_parser(
        "remove-image",
        help="Remove the background from one still image.",
    )
    remove_image_parser.add_argument("input", help="Path to an input image.")
    remove_image_parser.add_argument("output", help="Path for the processed RGBA PNG.")
    remove_image_parser.add_argument(
        "--model",
        choices=SUPPORTED_MODELS,
        default="isnet-anime",
        help="Background-removal model to use.",
    )
    remove_image_parser.add_argument(
        "--mask-output",
        help="Optional path for the raw alpha mask PNG.",
    )
    remove_image_parser.add_argument(
        "--model-cache-dir",
        default=".cache/rembg-models",
        help="Directory for downloaded rembg model files.",
    )

    benchmark_parser = subparsers.add_parser(
        "benchmark-image",
        help="Run one still image through one or more candidate models.",
    )
    benchmark_parser.add_argument("input", help="Path to an input image.")
    benchmark_parser.add_argument("output_dir", help="Directory for model outputs and masks.")
    benchmark_parser.add_argument(
        "--models",
        nargs="+",
        choices=SUPPORTED_MODELS,
        default=list(SUPPORTED_MODELS),
        help="Models to benchmark. Defaults to all Phase 2 candidates.",
    )
    benchmark_parser.add_argument(
        "--model-cache-dir",
        default=".cache/rembg-models",
        help="Directory for downloaded rembg model files.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "inspect":
            return _inspect(args.input)
        if args.command == "rebuild-noop":
            return _rebuild_noop(args.input, args.output)
        if args.command == "remove-image":
            return _remove_image(
                args.input,
                args.output,
                args.model,
                args.mask_output,
                args.model_cache_dir,
            )
        if args.command == "benchmark-image":
            return _benchmark_image(args.input, args.output_dir, args.models, args.model_cache_dir)
    except (AsepriteError, BackgroundRemovalError) as error:
        parser.exit(1, f"error: {error}\n")

    parser.error(f"command '{args.command}' is planned but not implemented yet")
    return 2


def _inspect(input_path: str) -> int:
    sprite = read_aseprite(input_path)
    print(f"File: {input_path}")
    print(f"Canvas: {sprite.width}x{sprite.height}")
    print(f"Color depth: {sprite.color_depth} bpp")
    print(f"Frames: {sprite.frame_count}")
    print("Frame durations: " + ", ".join(str(frame.duration_ms) for frame in sprite.frames))
    print(f"Layers: {len(sprite.layers)}")
    for layer in sprite.layers:
        visible = "visible" if layer.visible else "hidden"
        print(
            f"  [{layer.index}] {layer.name} "
            f"type={layer.layer_type} opacity={layer.opacity} blend={layer.blend_mode} {visible}"
        )
    print(f"Tags: {len(sprite.tags)}")
    for tag in sprite.tags:
        print(
            f"  {tag.name}: {tag.from_frame}-{tag.to_frame} "
            f"direction={tag.direction} repeat={tag.repeat}"
        )
    return 0


def _rebuild_noop(input_path: str, output_path: str) -> int:
    sprite = read_aseprite(input_path)
    frames = flatten_frames(sprite)
    durations = [frame.duration_ms for frame in sprite.frames]
    output = Path(output_path)
    if output.parent and str(output.parent) != ".":
        output.parent.mkdir(parents=True, exist_ok=True)
    write_flattened_aseprite(
        str(output),
        width=sprite.width,
        height=sprite.height,
        frame_pixels=frames,
        durations_ms=durations,
        tags=sprite.tags,
    )
    print(f"Wrote {output}")
    print(f"Frames: {len(frames)}")
    print(f"Canvas: {sprite.width}x{sprite.height}")
    return 0


def _remove_image(
    input_path: str,
    output_path: str,
    model_name: str,
    mask_output_path: str | None,
    model_cache_dir: str,
) -> int:
    from background_remover.background import remove_image_file

    result = remove_image_file(
        input_path=input_path,
        output_path=output_path,
        model_name=model_name,
        mask_output_path=mask_output_path,
        model_cache_dir=model_cache_dir,
    )
    print(f"Wrote {output_path}")
    if mask_output_path:
        print(f"Wrote {mask_output_path}")
    print(f"Model: {model_name}")
    print(f"Model cache: {model_cache_dir}")
    print(f"Time: {result.elapsed_seconds:.2f}s")
    return 0


def _benchmark_image(
    input_path: str,
    output_dir: str,
    model_names: list[str],
    model_cache_dir: str,
) -> int:
    from background_remover.background import benchmark_image_file

    results = benchmark_image_file(input_path, output_dir, model_names, model_cache_dir=model_cache_dir)
    print("model,seconds")
    for model_name, result in results:
        print(f"{model_name},{result.elapsed_seconds:.2f}")
    print(f"Wrote outputs to {output_dir}")
    print(f"Model cache: {model_cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
