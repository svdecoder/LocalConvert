"""Audio-only conversion, built on FFmpeg."""

from __future__ import annotations

from typing import Callable, Optional

from app.converters.base import BaseConverter
from app.engines import ffmpeg_engine
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

logger = get_logger("converters.audio")

_AUDIO_FORMATS = {"mp3", "aac", "wav", "flac", "ogg", "m4a"}
_LOSSLESS = {"wav", "flac"}

_DEFAULT_CODEC = {
    "mp3": "libmp3lame", "aac": "aac", "wav": "pcm_s16le",
    "flac": "flac", "ogg": "libvorbis", "m4a": "aac",
}


class AudioConverter(BaseConverter):
    name = "audio"

    def capabilities(self) -> list[CapabilityInfo]:
        return [
            CapabilityInfo(
                input_formats=_AUDIO_FORMATS | {"mp4", "mkv", "webm", "avi", "mov"},  # can extract audio from video
                output_formats=_AUDIO_FORMATS,
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(metadata=True),
                required_tools=["ffmpeg", "ffprobe"],
                limitations=[
                    "Converting from a lossy format (MP3, AAC, OGG) to another lossy or "
                    "even lossless format cannot recover quality already lost in the source.",
                ],
                options=[
                    ConversionOption(key="audio_codec", label="Codec", kind="choice", default="auto",
                                      choices=["auto", "libmp3lame", "aac", "pcm_s16le", "flac", "libvorbis", "copy"]),
                    ConversionOption(key="audio_bitrate", label="Bitrate (e.g. 192k)", kind="text", default="192k"),
                    ConversionOption(key="sample_rate", label="Sample rate (Hz)", kind="choice",
                                      default="original", choices=["original", "44100", "48000"]),
                    ConversionOption(key="preserve_metadata", label="Preserve metadata (tags)", kind="bool", default=True),
                ],
                backend_name="FFmpeg",
            )
        ]

    def convert(
        self,
        job: ConversionJob,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ConversionResult:
        if not ffmpeg_engine.is_available():
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="FFmpeg is required for audio conversion but was not found.",
            )

        out_fmt = job.output_format.lower().lstrip(".")
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{out_fmt}")
        warnings: list[ConversionWarning] = []

        opts = job.options
        codec = opts.get("audio_codec", "auto")
        if codec in (None, "auto"):
            codec = _DEFAULT_CODEC.get(out_fmt, "aac")

        extra_args = []
        sample_rate = opts.get("sample_rate")
        if sample_rate not in (None, "original"):
            extra_args += ["-ar", str(sample_rate)]

        transcode_opts = ffmpeg_engine.TranscodeOptions(
            video_codec=None,
            audio_codec=codec,
            audio_bitrate=None if out_fmt in _LOSSLESS else (opts.get("audio_bitrate") or "192k"),
            subtitle_mode="drop",
            preserve_chapters=False,
            preserve_metadata=bool(opts.get("preserve_metadata", True)),
            extra_args=extra_args + ["-vn"],  # strip any video stream (e.g. extracting audio from a video file)
        )

        if job.input_format in {"mp4", "mkv", "webm", "avi", "mov"}:
            warnings.append(ConversionWarning(
                "Source is a video file; only its audio track was extracted.", severity="info"
            ))

        try:
            ffmpeg_engine.run_transcode(
                job.input_path, final_path, transcode_opts,
                progress_cb=progress_cb, cancel_check=cancel_check,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Audio conversion failed")
            return ConversionResult(job_id=job.job_id, success=False, output_path=None, error_message=str(exc))

        if job.input_format in _AUDIO_FORMATS - _LOSSLESS and out_fmt in _LOSSLESS:
            warnings.append(ConversionWarning(
                f"Source ({job.input_format.upper()}) is already lossy; converting to "
                f"{out_fmt.upper()} increases file size without recovering lost quality.",
                severity="info",
            ))

        issues = ffmpeg_engine.validate_transcode_output(final_path, None, transcode_opts)
        if progress_cb:
            progress_cb(1.0, "Done")

        return ConversionResult(
            job_id=job.job_id,
            success=final_path.exists() and final_path.stat().st_size > 0,
            output_path=final_path,
            preserved=PreservationFlags(metadata=transcode_opts.preserve_metadata),
            warnings=warnings,
            validation_issues=issues,
            backend_used="FFmpeg",
        )
