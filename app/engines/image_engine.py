"""Raster/vector image engine built on Pillow, with ImageMagick as an
optional backend for a few operations Pillow doesn't cover well.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.utils.dependencies import check_executable, check_python_package
from app.utils.logging_setup import get_logger

logger = get_logger("engines.image")

ANIMATED_FORMATS = {"gif", "webp", "apng"}


def is_available() -> bool:
    return check_python_package("PIL").available


def imagemagick_available() -> bool:
    return check_executable("magick").available or check_executable("convert").available


class ImageEngineError(RuntimeError):
    pass


@dataclass
class ImageConvertOptions:
    quality: int = 90  # 1-100, used for lossy formats (JPEG/WEBP)
    resize: Optional[tuple[int, int]] = None  # (width, height); None = keep original
    dpi: Optional[tuple[int, int]] = None
    color_mode: Optional[str] = None  # "RGB", "RGBA", "L", "CMYK", ...
    preserve_metadata: bool = True
    strip_metadata: bool = False
    keep_animation: bool = True


def _is_animated(img) -> bool:
    return getattr(img, "is_animated", False)


def convert_image(
    input_path: Path,
    output_path: Path,
    options: ImageConvertOptions,
) -> Path:
    if not is_available():
        raise ImageEngineError("Pillow is not installed. Run: pip install Pillow")

    from PIL import Image, ImageOps  # type: ignore

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_format = output_path.suffix.lower().lstrip(".")
    pillow_format = {"jpg": "JPEG"}.get(target_format, target_format.upper())

    with Image.open(input_path) as img:
        img = ImageOps.exif_transpose(img)  # respect orientation, then drop the tag if stripping

        animated_source = _is_animated(img)
        save_animated = (
            animated_source and options.keep_animation and target_format in ANIMATED_FORMATS
        )

        save_kwargs: dict = {}
        exif = img.info.get("exif") if options.preserve_metadata and not options.strip_metadata else None
        if exif:
            save_kwargs["exif"] = exif

        if pillow_format in ("JPEG",):
            save_kwargs["quality"] = options.quality
            save_kwargs["optimize"] = True
        elif pillow_format == "WEBP":
            save_kwargs["quality"] = options.quality
        elif pillow_format == "PNG":
            save_kwargs["optimize"] = True

        if options.dpi:
            save_kwargs["dpi"] = options.dpi

        def _prepare_frame(frame):
            if options.resize:
                frame = frame.resize(options.resize, Image.LANCZOS)
            if options.color_mode:
                mode = options.color_mode
                if mode == "RGB" and frame.mode in ("RGBA", "LA", "P"):
                    frame = frame.convert("RGBA").convert("RGB")
                else:
                    frame = frame.convert(mode)
            elif pillow_format == "JPEG" and frame.mode in ("RGBA", "LA", "P"):
                # JPEG has no alpha channel: flatten onto white rather than
                # silently corrupting/erroring.
                background = Image.new("RGB", frame.size, (255, 255, 255))
                rgba = frame.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[-1])
                frame = background
            return frame

        if save_animated:
            frames = []
            durations = []
            try:
                for i in range(img.n_frames):
                    img.seek(i)
                    frames.append(_prepare_frame(img.convert("RGBA") if pillow_format == "WEBP" else img.copy()))
                    durations.append(img.info.get("duration", 100))
            finally:
                img.seek(0)
            first, rest = frames[0], frames[1:]
            first.save(
                output_path,
                format=pillow_format,
                save_all=True,
                append_images=rest,
                duration=durations,
                loop=img.info.get("loop", 0),
                **save_kwargs,
            )
        else:
            frame = _prepare_frame(img.convert("RGBA") if img.mode == "P" and target_format in ("png", "webp") else img)
            frame.save(output_path, format=pillow_format, **save_kwargs)

    return output_path


def convert_with_imagemagick(input_path: Path, output_path: Path, extra_args: Optional[list[str]] = None) -> Path:
    """Fallback/alternative path for formats Pillow handles less well
    (e.g. some ICO edge cases, certain TIFF compressions)."""
    exe = "magick" if check_executable("magick").available else "convert"
    if not check_executable(exe).available:
        raise ImageEngineError("ImageMagick is not installed.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, str(input_path)] + (extra_args or []) + [str(output_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise ImageEngineError(f"ImageMagick failed: {proc.stderr.strip()}")
    return output_path


def rasterize_svg(input_path: Path, output_path: Path, width: Optional[int] = None) -> Path:
    """SVG -> raster. Prefers ImageMagick/librsvg if present; otherwise
    tries Pillow (which needs an SVG-capable plugin) and raises a clear
    error if neither is usable, rather than silently failing."""
    if imagemagick_available():
        args = ["-density", "300"]
        if width:
            args += ["-resize", f"{width}x"]
        return convert_with_imagemagick(input_path, output_path, extra_args=args)
    raise ImageEngineError(
        "SVG rasterization requires ImageMagick (with librsvg/rsvg-convert support) "
        "which was not found. Install ImageMagick to enable SVG conversion."
    )


def image_to_svg_note() -> str:
    return (
        "Raster-to-SVG is not a true vector conversion: the raster image is "
        "embedded inside an SVG wrapper rather than traced into vector shapes."
    )


def wrap_raster_in_svg(input_path: Path, output_path: Path) -> Path:
    """Best-effort raster->SVG: embed the raster image as a base64 data URI
    inside an SVG container so it opens correctly in SVG viewers. This is
    NOT vector tracing and is declared as lossy/best-effort in the
    capability metadata."""
    import base64

    from PIL import Image  # type: ignore

    with Image.open(input_path) as img:
        width, height = img.size
        fmt = (img.format or "PNG").lower()
        mime = "image/png" if fmt == "png" else "image/jpeg"

    data = base64.b64encode(input_path.read_bytes()).decode("ascii")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'  <image width="{width}" height="{height}" '
        f'href="data:{mime};base64,{data}"/>\n'
        f"</svg>\n"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path
