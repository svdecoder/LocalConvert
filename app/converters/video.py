"""Video conversion, built on FFmpeg. Also handles the audio-track and
subtitle-track preservation logic described in the spec."""

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

logger = get_logger("converters.video")

_VIDEO_FORMATS = {"mp4", "mkv", "webm", "avi", "mov", "wmv", "mpeg", "mpg", "ts"}

_DEFAULT_VIDEO_CODEC = {
    "mp4": "libx264", "mov": "libx264", "mkv": "libx264", "avi": "mpeg4",
    "webm": "libvpx-vp9", "wmv": "wmv2", "mpeg": "mpeg2video", "mpg": "mpeg2video", "ts": "libx264",
}
_DEFAULT_AUDIO_CODEC = {
    "mp4": "aac", "mov": "aac", "mkv": "aac", "avi": "mp3",
    "webm": "libopus", "wmv": "wmav2", "mpeg": "mp2", "mpg": "mp2", "ts": "aac",
}


class VideoConverter(BaseConverter):
    name = "video"

    def capabilities(self) -> list[CapabilityInfo]:
        return [
            CapabilityInfo(
                input_formats=_VIDEO_FORMATS,
                output_formats=_VIDEO_FORMATS,
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(
                    subtitles=True, audio_tracks=True, chapters_video=True, metadata=True,
                ),
                required_tools=["ffmpeg", "ffprobe"],
                limitations=[
                    "Subtitle tracks can only be embedded in containers that support them "
                    "(MP4, MOV, MKV); other targets drop or require burning them in.",
                    "Re-encoding is lossy by nature (unless using 'copy' codec mode); "
                    "repeated re-encodes will accumulate quality loss.",
                    "Hardware-accelerated encoding availability depends on the local GPU/drivers.",
                ],
                options=[
                    ConversionOption(key="video_codec", label="Video codec", kind="choice", default="auto",
                                      choices=["auto", "libx264", "libx265", "libvpx-vp9", "mpeg4", "copy"]),
                    ConversionOption(key="audio_codec", label="Audio codec", kind="choice", default="auto",
                                      choices=["auto", "aac", "libmp3lame", "libopus", "flac", "copy"]),
                    ConversionOption(key="resolution", label="Resolution", kind="choice", default="original",
                                      choices=["original", "3840x2160", "1920x1080", "1280x720", "854x480"]),
                    ConversionOption(key="fps", label="Frame rate", kind="choice", default="original",
                                      choices=["original", "60", "30", "25", "24"]),
                    ConversionOption(key="crf", label="Quality (CRF, lower = better)", kind="int",
                                      default=23, minimum=0, maximum=51),
                    ConversionOption(key="video_bitrate", label="Video bitrate (e.g. 4M)", kind="text", default=""),
                    ConversionOption(key="audio_bitrate", label="Audio bitrate (e.g. 192k)", kind="text", default="192k"),
                    ConversionOption(key="hardware_accel", label="Hardware acceleration", kind="choice",
                                      default="none", choices=["none", "auto", "videotoolbox", "cuda", "qsv", "vaapi"]),
                    ConversionOption(key="subtitle_mode", label="Subtitles", kind="choice",
                                      default="embed_if_supported",
                                      choices=["embed_if_supported", "drop"]),
                    ConversionOption(key="preserve_chapters", label="Preserve chapters", kind="bool", default=True),
                    ConversionOption(key="preserve_metadata", label="Preserve metadata", kind="bool", default=True),
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
                error_message="FFmpeg is required for video conversion but was not found.",
            )

        out_fmt = job.output_format.lower().lstrip(".")
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{out_fmt}")
        warnings: list[ConversionWarning] = []

        opts = job.options
        video_codec = opts.get("video_codec", "auto")
        audio_codec = opts.get("audio_codec", "auto")
        if video_codec in (None, "auto"):
            video_codec = _DEFAULT_VIDEO_CODEC.get(out_fmt, "libx264")
        if audio_codec in (None, "auto"):
            audio_codec = _DEFAULT_AUDIO_CODEC.get(out_fmt, "aac")

        resolution = opts.get("resolution")
        resolution = None if resolution in (None, "original") else resolution
        fps = opts.get("fps")
        fps = None if fps in (None, "original") else float(fps)
        hw = opts.get("hardware_accel", "none")
        hw = None if hw in (None, "none") else hw

        transcode_opts = ffmpeg_engine.TranscodeOptions(
            video_codec=video_codec,
            audio_codec=audio_codec,
            resolution=resolution,
            fps=fps,
            video_bitrate=opts.get("video_bitrate") or None,
            audio_bitrate=opts.get("audio_bitrate") or None,
            crf=int(opts["crf"]) if opts.get("crf") not in (None, "") else 23,
            hardware_accel=hw,
            subtitle_mode=opts.get("subtitle_mode", "embed_if_supported"),
            preserve_chapters=bool(opts.get("preserve_chapters", True)),
            preserve_metadata=bool(opts.get("preserve_metadata", True)),
        )

        source_probe = None
        try:
            if ffmpeg_engine.ffprobe_available():
                source_probe = ffmpeg_engine.probe(job.input_path)
        except Exception:
            source_probe = None

        try:
            ffmpeg_engine.run_transcode(
                job.input_path, final_path, transcode_opts,
                progress_cb=progress_cb, cancel_check=cancel_check,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video conversion failed")
            return ConversionResult(job_id=job.job_id, success=False, output_path=None, error_message=str(exc))

        target_supports_subs = out_fmt in ffmpeg_engine._SUBTITLE_CAPABLE_CONTAINERS
        if source_probe and source_probe.subtitle_streams and not target_supports_subs:
            warnings.append(ConversionWarning(
                f"The {out_fmt.upper()} container does not support embedded subtitles; "
                "subtitle tracks were dropped. Consider MKV or MP4 if you need them.",
                severity="warning",
            ))

        issues = ffmpeg_engine.validate_transcode_output(final_path, source_probe, transcode_opts)

        if progress_cb:
            progress_cb(1.0, "Done")

        return ConversionResult(
            job_id=job.job_id,
            success=not any("no video" in i.lower() or "no audio" in i.lower() for i in issues),
            output_path=final_path,
            preserved=PreservationFlags(
                subtitles=target_supports_subs and bool(source_probe and source_probe.subtitle_streams),
                audio_tracks=True,
                chapters_video=transcode_opts.preserve_chapters,
                metadata=transcode_opts.preserve_metadata,
            ),
            warnings=warnings,
            validation_issues=issues,
            backend_used="FFmpeg",
            error_message="; ".join(issues) if issues else "",
        )
