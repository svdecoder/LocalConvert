"""Raster and basic vector image conversion."""

from __future__ import annotations

from typing import Callable, Optional

from app.converters.base import BaseConverter
from app.engines import image_engine
from app.models import (
    CapabilityInfo,
    ConversionJob,
    ConversionOption,
    ConversionResult,
    ConversionWarning,
    Fidelity,
    PreservationFlags,
)
from app.utils.fs import unique_output_path
from app.utils.logging_setup import get_logger

logger = get_logger("converters.images")

_RASTER_FORMATS = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "ico"}
_LOSSY_TARGETS = {"jpg", "jpeg", "webp"}


class ImageConverter(BaseConverter):
    name = "images"

    def capabilities(self) -> list[CapabilityInfo]:
        common_options = [
            ConversionOption(key="quality", label="Quality", kind="int", default=90, minimum=1, maximum=100,
                              help_text="Used for lossy formats (JPEG/WEBP)."),
            ConversionOption(key="resize_width", label="Resize width (px)", kind="int", default=0,
                              help_text="0 = keep original size."),
            ConversionOption(key="resize_height", label="Resize height (px)", kind="int", default=0,
                              help_text="0 = keep original size."),
            ConversionOption(key="strip_metadata", label="Strip metadata (EXIF)", kind="bool", default=False),
            ConversionOption(key="keep_animation", label="Preserve animation", kind="bool", default=True),
            ConversionOption(key="color_mode", label="Color mode", kind="choice", default="auto",
                              choices=["auto", "RGB", "RGBA", "L", "CMYK"]),
        ]

        return [
            CapabilityInfo(
                input_formats=_RASTER_FORMATS,
                output_formats=_RASTER_FORMATS,
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(
                    transparency=True, animation=True, color_profile=True,
                ),
                required_tools=["py:PIL"],
                options=common_options,
                limitations=[
                    "Converting to JPEG discards transparency (flattened onto a white background).",
                    "Converting an animated image to a static-only format keeps only the first frame.",
                    "ICO output is limited to the small fixed sizes the format supports.",
                ],
                backend_name="Pillow",
            ),
            CapabilityInfo(
                input_formats={"svg"},
                output_formats={"png", "jpg", "jpeg", "webp", "bmp", "tiff"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(transparency=True),
                required_tools=["magick"],
                limitations=["Requires ImageMagick with SVG (librsvg) support installed locally."],
                options=[ConversionOption(key="resize_width", label="Output width (px)", kind="int", default=0)],
                backend_name="ImageMagick",
            ),
            CapabilityInfo(
                input_formats=_RASTER_FORMATS,
                output_formats={"svg"},
                fidelity=Fidelity.LOSSY,
                preserves=PreservationFlags(),
                required_tools=["py:PIL"],
                limitations=[
                    "This is not true vector tracing: the raster image is embedded "
                    "inside an SVG wrapper, not converted into vector shapes.",
                ],
                backend_name="Pillow (raster-in-SVG wrapper)",
            ),
        ]

    def convert(
        self,
        job: ConversionJob,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ConversionResult:
        in_fmt = job.input_format
        out_fmt = job.output_format.lower().lstrip(".")
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{out_fmt}")
        warnings: list[ConversionWarning] = []

        try:
            if in_fmt == "svg" and out_fmt != "svg":
                if progress_cb:
                    progress_cb(0.2, "Rasterizing SVG...")
                width = job.options.get("resize_width") or None
                image_engine.rasterize_svg(job.input_path, final_path, width=width)
                preserved = PreservationFlags(transparency=True)
                backend = "ImageMagick"

            elif out_fmt == "svg":
                if progress_cb:
                    progress_cb(0.2, "Wrapping raster image in SVG...")
                image_engine.wrap_raster_in_svg(job.input_path, final_path)
                warnings.append(ConversionWarning(image_engine.image_to_svg_note(), severity="warning"))
                preserved = PreservationFlags()
                backend = "Pillow"

            else:
                if progress_cb:
                    progress_cb(0.2, "Converting image...")
                resize = None
                w, h = job.options.get("resize_width", 0), job.options.get("resize_height", 0)
                if w and h:
                    resize = (int(w), int(h))
                color_mode = job.options.get("color_mode")
                color_mode = None if color_mode in (None, "auto") else color_mode

                options = image_engine.ImageConvertOptions(
                    quality=int(job.options.get("quality", 90)),
                    resize=resize,
                    color_mode=color_mode,
                    strip_metadata=bool(job.options.get("strip_metadata", False)),
                    preserve_metadata=not bool(job.options.get("strip_metadata", False)),
                    keep_animation=bool(job.options.get("keep_animation", True)),
                )
                image_engine.convert_image(job.input_path, final_path, options)
                preserved = PreservationFlags(
                    transparency=out_fmt not in ("jpg", "jpeg"),
                    animation=(in_fmt in image_engine.ANIMATED_FORMATS and out_fmt in image_engine.ANIMATED_FORMATS),
                    color_profile=not options.strip_metadata,
                )
                if out_fmt in _LOSSY_TARGETS and in_fmt not in _LOSSY_TARGETS:
                    warnings.append(ConversionWarning(
                        f"Converting to {out_fmt.upper()} applies lossy compression.", severity="info"
                    ))
                if in_fmt in image_engine.ANIMATED_FORMATS and out_fmt not in image_engine.ANIMATED_FORMATS:
                    warnings.append(ConversionWarning(
                        "Source is animated; only the first frame was kept because the "
                        "target format does not support animation.", severity="warning",
                    ))
                if out_fmt in ("jpg", "jpeg") and in_fmt in ("png", "webp", "gif", "tiff"):
                    warnings.append(ConversionWarning(
                        "Transparency was flattened onto a white background because JPEG "
                        "does not support an alpha channel.", severity="warning",
                    ))
                backend = "Pillow"

        except Exception as exc:  # noqa: BLE001
            logger.exception("Image conversion failed")
            return ConversionResult(job_id=job.job_id, success=False, output_path=None, error_message=str(exc))

        if not final_path.exists() or final_path.stat().st_size == 0:
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="Conversion reported success but produced no output file.",
            )

        if progress_cb:
            progress_cb(1.0, "Done")

        return ConversionResult(
            job_id=job.job_id, success=True, output_path=final_path,
            preserved=preserved, warnings=warnings, backend_used=backend,
        )
