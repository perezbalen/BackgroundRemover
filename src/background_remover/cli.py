"""Command-line entry point for the Aseprite background remover."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import time

from background_remover import __version__
from background_remover.aseprite import (
    AsepriteError,
    flatten_frames,
    read_aseprite,
    write_flattened_aseprite,
)
from background_remover.background import SUPPORTED_MODELS, BackgroundRemovalError
from background_remover.color_key import (
    ColorKeyOptions,
    apply_color_key_assist,
    describe_color_key_options,
    parse_rgb_color,
)
from background_remover.mask_cleanup import MaskCleanupOptions, apply_alpha_mask, apply_mask_cleanup
from background_remover.reporting import (
    build_processing_report,
    write_contact_sheet,
    write_gif_preview,
    write_processing_report,
)

LAYER_POLICY = "flattened processed layer"
OUTPUT_LAYER_NAME = "Flattened"
METADATA_POLICY = {
    "canvas_size": "preserved",
    "frame_order": "preserved",
    "frame_count": "preserved",
    "frame_duration": "preserved",
    "animation_tags": "preserved",
    "slices": "not preserved",
    "layer_names": "not preserved; output uses a single Flattened layer",
}


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
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List supported background-removal models and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect input sprite metadata.",
    )
    inspect_parser.add_argument("input", help="Path to an input .aseprite file.")
    _add_logging_arguments(inspect_parser)

    rebuild_parser = subparsers.add_parser(
        "rebuild-noop",
        help="Flatten and rebuild an .aseprite file without background removal.",
    )
    rebuild_parser.add_argument("input", help="Path to an input .aseprite file.")
    rebuild_parser.add_argument("output", help="Path for the rebuilt .aseprite file.")
    _add_output_arguments(rebuild_parser)
    _add_logging_arguments(rebuild_parser)

    process_parser = subparsers.add_parser(
        "process",
        help="Remove backgrounds from every frame in an .aseprite file.",
    )
    process_parser.add_argument("input", help="Path to an input .aseprite file.")
    process_parser.add_argument("output", help="Path for the processed .aseprite file.")
    process_parser.add_argument(
        "--model",
        choices=SUPPORTED_MODELS,
        default="isnet-anime",
        help="Background-removal model to use.",
    )
    process_parser.add_argument(
        "--frame-output-dir",
        help="Optional directory for processed RGBA frame PNGs.",
    )
    process_parser.add_argument(
        "--mask-output-dir",
        help="Optional directory for final combined alpha mask PNGs.",
    )
    process_parser.add_argument(
        "--ai-mask-output-dir",
        help="Optional directory for cleaned AI alpha mask PNGs before color-key assist.",
    )
    process_parser.add_argument(
        "--color-key-mask-output-dir",
        help="Optional directory for color-key foreground mask PNGs.",
    )
    process_parser.add_argument(
        "--model-cache-dir",
        default=".cache/rembg-models",
        help="Directory for downloaded rembg model files.",
    )
    process_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect input metadata and planned processing settings without loading a model.",
    )
    process_parser.add_argument(
        "--report-output",
        help="Optional path for a JSON report with per-frame mask metrics.",
    )
    process_parser.add_argument(
        "--contact-sheet-output",
        help="Optional path for a PNG contact sheet showing original, mask, and result frames.",
    )
    process_parser.add_argument(
        "--preview-output",
        help="Optional path for an animated GIF preview of processed frames.",
    )
    process_parser.add_argument(
        "--area-jump-threshold",
        type=float,
        default=0.25,
        help="Warn when neighboring frame mask area changes by more than this ratio.",
    )
    process_parser.add_argument(
        "--bbox-jump-threshold",
        type=float,
        default=32.0,
        help="Warn when neighboring bounding-box centers move by more than this many pixels.",
    )
    _add_output_arguments(process_parser)
    _add_logging_arguments(process_parser)
    _add_mask_cleanup_arguments(process_parser)
    _add_color_key_arguments(process_parser)

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
    _add_output_arguments(remove_image_parser)
    _add_logging_arguments(remove_image_parser)
    _add_mask_cleanup_arguments(remove_image_parser)

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
    _add_output_arguments(benchmark_parser)
    _add_logging_arguments(benchmark_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        return _list_models()

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "inspect":
            return _inspect(args.input, verbose=args.verbose, quiet=args.quiet)
        if args.command == "rebuild-noop":
            return _rebuild_noop(args.input, args.output, overwrite=args.overwrite)
        if args.command == "process":
            return _process_aseprite(
                args.input,
                args.output,
                args.model,
                args.frame_output_dir,
                args.mask_output_dir,
                args.ai_mask_output_dir,
                args.color_key_mask_output_dir,
                args.model_cache_dir,
                _cleanup_options_from_args(args),
                _color_key_options_from_args(args),
                args.report_output,
                args.contact_sheet_output,
                args.preview_output,
                args.area_jump_threshold,
                args.bbox_jump_threshold,
                args.dry_run,
                args.overwrite,
                args.verbose,
                args.quiet,
            )
        if args.command == "remove-image":
            return _remove_image(
                args.input,
                args.output,
                args.model,
                args.mask_output,
                args.model_cache_dir,
                _cleanup_options_from_args(args),
                args.overwrite,
                args.quiet,
            )
        if args.command == "benchmark-image":
            return _benchmark_image(
                args.input,
                args.output_dir,
                args.models,
                args.model_cache_dir,
                overwrite=args.overwrite,
                quiet=args.quiet,
            )
    except AsepriteError as error:
        parser.exit(1, f"error: unsupported .aseprite input: {error}\n")
    except BackgroundRemovalError as error:
        parser.exit(1, f"error: {error}\n")

    parser.error(f"unknown command '{args.command}'")
    return 2


def _list_models() -> int:
    for model_name in SUPPORTED_MODELS:
        print(model_name)
    return 0


def _inspect(input_path: str, verbose: int = 0, quiet: bool = False) -> int:
    _require_input_file(input_path, "Aseprite input")
    _validate_aseprite_extension(input_path)
    sprite = read_aseprite(input_path)
    if quiet:
        print(f"{input_path}: {sprite.frame_count} frame(s), {sprite.width}x{sprite.height}")
        return 0

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
    if verbose:
        print(f"Layer policy on process: {LAYER_POLICY}")
        print("Metadata policy:")
        for key, value in METADATA_POLICY.items():
            print(f"  {key}: {value}")
    return 0


def _rebuild_noop(input_path: str, output_path: str, overwrite: bool = False) -> int:
    _require_input_file(input_path, "Aseprite input")
    _validate_aseprite_extension(input_path)
    _prepare_output_file(output_path, overwrite=overwrite, label="output .aseprite")
    sprite = read_aseprite(input_path)
    frames = flatten_frames(sprite)
    durations = [frame.duration_ms for frame in sprite.frames]
    output = Path(output_path)
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


def _process_aseprite(
    input_path: str,
    output_path: str,
    model_name: str,
    frame_output_dir: str | None,
    mask_output_dir: str | None,
    ai_mask_output_dir: str | None,
    color_key_mask_output_dir: str | None,
    model_cache_dir: str,
    cleanup_options: MaskCleanupOptions,
    color_key_options: ColorKeyOptions,
    report_output_path: str | None,
    contact_sheet_output_path: str | None,
    preview_output_path: str | None,
    area_jump_threshold: float,
    bbox_jump_threshold: float,
    dry_run: bool,
    overwrite: bool,
    verbose: int,
    quiet: bool,
) -> int:
    try:
        from PIL import Image
    except ImportError as error:
        raise BackgroundRemovalError(
            "Missing Pillow dependency. Run: " 'python3 -m pip install -e ".[dev]"'
        ) from error

    from background_remover.background import RembgBackgroundRemover

    _require_input_file(input_path, "Aseprite input")
    _validate_aseprite_extension(input_path)

    total_started = time.perf_counter()
    sprite = read_aseprite(input_path)
    source_frames = flatten_frames(sprite)
    durations = [frame.duration_ms for frame in sprite.frames]

    cleanup_description = _describe_cleanup(cleanup_options)
    color_key_description = describe_color_key_options(color_key_options)

    if dry_run:
        _print_process_dry_run(
            input_path=input_path,
            output_path=output_path,
            sprite=sprite,
            model_name=model_name,
            model_cache_dir=model_cache_dir,
            cleanup_description=cleanup_description,
            color_key_description=color_key_description,
            verbose=verbose,
        )
        return 0

    _prepare_output_file(output_path, overwrite=overwrite, label="output .aseprite")
    for optional_path, label in (
        (report_output_path, "JSON report"),
        (contact_sheet_output_path, "contact sheet"),
        (preview_output_path, "animated preview"),
    ):
        if optional_path:
            _prepare_output_file(optional_path, overwrite=overwrite, label=label)

    frame_output = Path(frame_output_dir) if frame_output_dir else None
    mask_output = Path(mask_output_dir) if mask_output_dir else None
    ai_mask_output = Path(ai_mask_output_dir) if ai_mask_output_dir else None
    color_key_mask_output = Path(color_key_mask_output_dir) if color_key_mask_output_dir else None
    if frame_output:
        frame_output.mkdir(parents=True, exist_ok=True)
    if mask_output:
        mask_output.mkdir(parents=True, exist_ok=True)
    if ai_mask_output:
        ai_mask_output.mkdir(parents=True, exist_ok=True)
    if color_key_mask_output:
        color_key_mask_output.mkdir(parents=True, exist_ok=True)

    remover = RembgBackgroundRemover(model_name, model_cache_dir=model_cache_dir)
    processed_frames: list[bytes] = []
    original_images = []
    mask_images = []
    processed_images = []
    processing_elapsed = 0.0
    frame_count = len(source_frames)

    for index, pixels in enumerate(source_frames):
        image = Image.frombytes("RGBA", (sprite.width, sprite.height), pixels)
        result = remover.remove(image)
        if result.image.size != (sprite.width, sprite.height):
            raise BackgroundRemovalError(
                f"Model returned frame {index + 1} at {result.image.width}x{result.image.height}; "
                f"expected {sprite.width}x{sprite.height}"
            )

        try:
            cleaned_mask = apply_mask_cleanup(result.mask, cleanup_options)
            color_key_result = apply_color_key_assist(image, cleaned_mask, color_key_options)
        except ValueError as error:
            raise BackgroundRemovalError(str(error)) from error

        final_mask = color_key_result.combined_mask if color_key_result else cleaned_mask
        processed = apply_alpha_mask(result.image, final_mask)
        processed_frames.append(processed.tobytes())
        original_images.append(image.copy())
        mask_images.append(final_mask.copy())
        processed_images.append(processed.copy())
        processing_elapsed += result.elapsed_seconds

        frame_name = f"frame-{index:04d}.png"
        if frame_output:
            processed.save(frame_output / frame_name)
        if mask_output:
            final_mask.save(mask_output / frame_name)
        if ai_mask_output:
            cleaned_mask.save(ai_mask_output / frame_name)
        if color_key_mask_output and color_key_result:
            color_key_result.color_key_mask.save(color_key_mask_output / frame_name)

        if not quiet:
            print(
                f"Processed frame {index + 1}/{frame_count} "
                f"in {result.elapsed_seconds:.2f}s"
            )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_flattened_aseprite(
        str(output),
        width=sprite.width,
        height=sprite.height,
        frame_pixels=processed_frames,
        durations_ms=durations,
        tags=sprite.tags,
        layer_name=OUTPUT_LAYER_NAME,
    )

    total_elapsed = time.perf_counter() - total_started
    average_elapsed = processing_elapsed / frame_count if frame_count else 0.0
    report = build_processing_report(
        input_path=input_path,
        output_path=str(output),
        model_name=model_name,
        cleanup=cleanup_description,
        color_key=color_key_description,
        layer_policy=LAYER_POLICY,
        metadata_policy=METADATA_POLICY,
        width=sprite.width,
        height=sprite.height,
        durations_ms=durations,
        masks=mask_images,
        processing_seconds=processing_elapsed,
        total_seconds=total_elapsed,
        area_jump_threshold=area_jump_threshold,
        bbox_jump_threshold=bbox_jump_threshold,
    )

    if report_output_path:
        write_processing_report(report_output_path, report)
    if contact_sheet_output_path:
        write_contact_sheet(contact_sheet_output_path, original_images, mask_images, processed_images)
    if preview_output_path:
        write_gif_preview(preview_output_path, processed_images, durations)

    if not quiet:
        for warning in report["warnings"]:
            print(f"warning: {warning['message']}")
        print(
            "warning: output is flattened into one processed layer; "
            "original layer names are not preserved"
        )

    print(f"Wrote {output}")
    if quiet:
        return 0
    if frame_output:
        print(f"Wrote processed frames to {frame_output}")
    if mask_output:
        print(f"Wrote masks to {mask_output}")
    if ai_mask_output:
        print(f"Wrote AI masks to {ai_mask_output}")
    if color_key_mask_output:
        print(f"Wrote color-key masks to {color_key_mask_output}")
    if report_output_path:
        print(f"Wrote report to {report_output_path}")
    if contact_sheet_output_path:
        print(f"Wrote contact sheet to {contact_sheet_output_path}")
    if preview_output_path:
        print(f"Wrote preview to {preview_output_path}")
    print(f"Model: {model_name}")
    print(f"Model cache: {model_cache_dir}")
    print(f"Cleanup: {cleanup_description}")
    print(f"Color key: {color_key_description}")
    print(f"Layer policy: {LAYER_POLICY}")
    print("Metadata: canvas, frame order, frame durations, and animation tags preserved")
    if verbose:
        print("Metadata policy:")
        for key, value in METADATA_POLICY.items():
            print(f"  {key}: {value}")
    print(f"Temporal warnings: {len(report['warnings'])}")
    print(f"Frames: {frame_count}")
    print(f"Canvas: {sprite.width}x{sprite.height}")
    print(f"Processing time: {processing_elapsed:.2f}s")
    print(f"Average frame time: {average_elapsed:.2f}s")
    print(f"Total time: {total_elapsed:.2f}s")
    return 0


def _remove_image(
    input_path: str,
    output_path: str,
    model_name: str,
    mask_output_path: str | None,
    model_cache_dir: str,
    cleanup_options: MaskCleanupOptions,
    overwrite: bool,
    quiet: bool,
) -> int:
    from background_remover.background import remove_image_file

    _require_input_file(input_path, "image input")
    _prepare_output_file(output_path, overwrite=overwrite, label="output image")
    if mask_output_path:
        _prepare_output_file(mask_output_path, overwrite=overwrite, label="mask output")

    result = remove_image_file(
        input_path=input_path,
        output_path=output_path,
        model_name=model_name,
        mask_output_path=mask_output_path,
        model_cache_dir=model_cache_dir,
        cleanup_options=cleanup_options,
    )
    print(f"Wrote {output_path}")
    if quiet:
        return 0
    if mask_output_path:
        print(f"Wrote {mask_output_path}")
    print(f"Model: {model_name}")
    print(f"Model cache: {model_cache_dir}")
    print(f"Cleanup: {_describe_cleanup(cleanup_options)}")
    print(f"Time: {result.elapsed_seconds:.2f}s")
    return 0


def _benchmark_image(
    input_path: str,
    output_dir: str,
    model_names: list[str],
    model_cache_dir: str,
    overwrite: bool = False,
    quiet: bool = False,
) -> int:
    from background_remover.background import benchmark_image_file

    _require_input_file(input_path, "image input")
    output = Path(output_dir)
    for model_name in model_names:
        _prepare_output_file(
            output / f"{model_name}.png",
            overwrite=overwrite,
            label=f"{model_name} output image",
        )
        _prepare_output_file(
            output / f"{model_name}.mask.png",
            overwrite=overwrite,
            label=f"{model_name} mask output",
        )

    results = benchmark_image_file(input_path, output_dir, model_names, model_cache_dir=model_cache_dir)
    if quiet:
        print(f"Wrote outputs to {output_dir}")
        return 0
    print("model,seconds")
    for model_name, result in results:
        print(f"{model_name},{result.elapsed_seconds:.2f}")
    print(f"Wrote outputs to {output_dir}")
    print(f"Model cache: {model_cache_dir}")
    return 0


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing output files.",
    )


def _add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only essential command output.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Print additional diagnostic information.",
    )


def _add_mask_cleanup_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Disable mask cleanup and use the raw model alpha output.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        help="Optional alpha threshold from 0 to 255. Pixels below it become transparent.",
    )
    parser.add_argument(
        "--min-artifact-size",
        type=int,
        default=4,
        help="Remove isolated foreground components smaller than this many pixels. Use 0 to disable.",
    )
    parser.add_argument(
        "--fill-hole-size",
        type=int,
        default=4,
        help="Fill enclosed transparent holes up to this many pixels. Use 0 to disable.",
    )
    parser.add_argument(
        "--keep-largest-component",
        action="store_true",
        help="Keep only the largest connected foreground component.",
    )
    parser.add_argument(
        "--feather-radius",
        type=float,
        default=0.0,
        help="Apply Gaussian feathering to the cleaned alpha mask. Use 0 to disable.",
    )


def _add_color_key_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--color-key-sample-corners",
        action="store_true",
        help="Enable color-key assist by sampling the background color from frame corners.",
    )
    parser.add_argument(
        "--color-key-color",
        help="Enable color-key assist with a user-provided background color, as '#RRGGBB' or 'R,G,B'.",
    )
    parser.add_argument(
        "--color-key-tolerance",
        type=float,
        default=24.0,
        help="RGB distance tolerance for near-solid background removal.",
    )
    parser.add_argument(
        "--color-key-protect-alpha",
        type=int,
        default=224,
        help="Keep pixels whose AI alpha is at least this value, even if color-key matches.",
    )


def _cleanup_options_from_args(args: argparse.Namespace) -> MaskCleanupOptions:
    return MaskCleanupOptions(
        enabled=not args.no_cleanup,
        alpha_threshold=args.alpha_threshold,
        min_artifact_size=args.min_artifact_size,
        fill_hole_size=args.fill_hole_size,
        keep_largest_component=args.keep_largest_component,
        feather_radius=args.feather_radius,
    )


def _color_key_options_from_args(args: argparse.Namespace) -> ColorKeyOptions:
    color = None
    if args.color_key_color:
        try:
            color = parse_rgb_color(args.color_key_color)
        except ValueError as error:
            raise BackgroundRemovalError(str(error)) from error

    return ColorKeyOptions(
        enabled=args.color_key_sample_corners or color is not None,
        sample_corners=args.color_key_sample_corners and color is None,
        color=color,
        tolerance=args.color_key_tolerance,
        protect_alpha=args.color_key_protect_alpha,
    )


def _describe_cleanup(options: MaskCleanupOptions) -> str:
    if not options.enabled:
        return "disabled"
    threshold = "none" if options.alpha_threshold is None else str(options.alpha_threshold)
    return (
        f"alpha_threshold={threshold}, "
        f"min_artifact_size={options.min_artifact_size}, "
        f"fill_hole_size={options.fill_hole_size}, "
        f"keep_largest_component={options.keep_largest_component}, "
        f"feather_radius={options.feather_radius:g}"
    )


def _require_input_file(path: str, label: str) -> None:
    input_path = Path(path)
    if not input_path.exists():
        raise BackgroundRemovalError(f"Missing {label}: {input_path}")
    if not input_path.is_file():
        raise BackgroundRemovalError(f"{label} is not a file: {input_path}")


def _validate_aseprite_extension(path: str) -> None:
    if Path(path).suffix.lower() != ".aseprite":
        raise BackgroundRemovalError(f"Unsupported input extension for .aseprite command: {path}")


def _prepare_output_file(path: str | Path, *, overwrite: bool, label: str) -> None:
    output = Path(path)
    if output.exists() and not overwrite:
        raise BackgroundRemovalError(f"{label} already exists: {output} (use --overwrite to replace it)")
    if output.parent and str(output.parent) != ".":
        output.parent.mkdir(parents=True, exist_ok=True)


def _print_process_dry_run(
    *,
    input_path: str,
    output_path: str,
    sprite,
    model_name: str,
    model_cache_dir: str,
    cleanup_description: str,
    color_key_description: str,
    verbose: int,
) -> None:
    print(f"Dry run: {input_path}")
    print(f"Planned output: {output_path}")
    print(f"Canvas: {sprite.width}x{sprite.height}")
    print(f"Frames: {sprite.frame_count}")
    print("Frame durations: " + ", ".join(str(frame.duration_ms) for frame in sprite.frames))
    print(f"Tags: {len(sprite.tags)}")
    for tag in sprite.tags:
        print(f"  {tag.name}: {tag.from_frame}-{tag.to_frame}")
    print(f"Model: {model_name}")
    print(f"Model cache: {model_cache_dir}")
    print(f"Cleanup: {cleanup_description}")
    print(f"Color key: {color_key_description}")
    print(f"Layer policy: {LAYER_POLICY}")
    if verbose:
        print("Metadata policy:")
        for key, value in METADATA_POLICY.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
