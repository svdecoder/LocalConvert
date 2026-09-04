"""FFmpeg/ffprobe engine for video and audio conversion.

Everything here shells out to the local ``ffmpeg``/``ffprobe``
executables — no bundled/compiled bindings, so whatever codecs the
user's local FFmpeg build supports are what we support, and we report
missing codecs honestly rather than pretending.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app.utils.dependencies import check_executable
from app.utils.logging_setup import get_logger

logger = get_logger("engines.ffmpeg")

_DURATION_RE = re.compile(r"Duration: (\d+):(\d+):(\d+\.\d+)")
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


def is_available() -> bool:
    return check_executable("ffmpeg").available


def ffprobe_available() -> bool:
    return check_executable("ffprobe").available


class FfmpegError(RuntimeError):
    pass


@dataclass
class StreamInfo:
    index: int
    codec_type: str  # "video" | "audio" | "subtitle"
    codec_name: str
    language: str = ""
    title: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class MediaProbe:
    duration_seconds: float
    format_name: str
    streams: list[StreamInfo]
    chapters: list[dict]
    tags: dict

    @property
    def video_streams(self) -> list[StreamInfo]:
        return [s for s in self.streams if s.codec_type == "video"]

    @property
    def audio_streams(self) -> list[StreamInfo]:
        return [s for s in self.streams if s.codec_type == "audio"]

    @property
    def subtitle_streams(self) -> list[StreamInfo]:
        return [s for s in self.streams if s.codec_type == "subtitle"]


def probe(path: Path) -> MediaProbe:
    status = check_executable("ffprobe")
    if not status.available:
        raise FfmpegError("ffprobe was not found on PATH (it ships with FFmpeg).")

    cmd = [
        status.path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise FfmpegError(f"ffprobe failed: {proc.stderr.strip()}")

    data = json.loads(proc.stdout or "{}")
    fmt = data.get("format", {})
    streams = []
    for s in data.get("streams", []):
        tags = s.get("tags", {})
        streams.append(
            StreamInfo(
                index=s.get("index", 0),
                codec_type=s.get("codec_type", "unknown"),
                codec_name=s.get("codec_name", "unknown"),
                language=tags.get("language", ""),
                title=tags.get("title", ""),
                extra=s,
            )
        )
    return MediaProbe(
        duration_seconds=float(fmt.get("duration", 0.0) or 0.0),
        format_name=fmt.get("format_name", ""),
        streams=streams,
        chapters=data.get("chapters", []),
        tags=fmt.get("tags", {}),
    )


@dataclass
class TranscodeOptions:
    video_codec: Optional[str] = None       # e.g. "libx264", "libx265", "copy"
    audio_codec: Optional[str] = None       # e.g. "aac", "libmp3lame", "copy"
    resolution: Optional[str] = None        # e.g. "1920x1080"
    fps: Optional[float] = None
    video_bitrate: Optional[str] = None     # e.g. "4M"
    audio_bitrate: Optional[str] = None     # e.g. "192k"
    crf: Optional[int] = None               # quality (codec-dependent scale)
    container: Optional[str] = None         # explicit -f override if needed
    hardware_accel: Optional[str] = None    # e.g. "auto", "videotoolbox", "nvenc", "qsv"
    subtitle_mode: str = "embed_if_supported"  # "embed_if_supported" | "burn_in" | "drop" | "extract_srt"
    audio_track_indices: Optional[list[int]] = None  # None = all
    subtitle_track_indices: Optional[list[int]] = None  # None = all
    preserve_chapters: bool = True
    preserve_metadata: bool = True
    extra_args: list[str] = field(default_factory=list)


_SUBTITLE_CAPABLE_CONTAINERS = {"mkv", "mp4", "mov"}


def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    options: TranscodeOptions,
    media_probe: Optional[MediaProbe] = None,
) -> list[str]:
    status = check_executable("ffmpeg")
    cmd = [status.path, "-y", "-hide_banner"]

    if options.hardware_accel and options.hardware_accel != "none":
        cmd += ["-hwaccel", options.hardware_accel]

    cmd += ["-i", str(input_path)]

    # Stream mapping: default to "all streams of the kinds we understand",
    # narrowed by explicit track selection when provided.
    cmd += ["-map", "0:v?"]
    if options.audio_track_indices:
        for idx in options.audio_track_indices:
            cmd += ["-map", f"0:{idx}"]
    else:
        cmd += ["-map", "0:a?"]

    target_ext = output_path.suffix.lower().lstrip(".")
    subtitles_supported = target_ext in _SUBTITLE_CAPABLE_CONTAINERS

    if options.subtitle_mode == "embed_if_supported" and subtitles_supported:
        if options.subtitle_track_indices:
            for idx in options.subtitle_track_indices:
                cmd += ["-map", f"0:{idx}"]
        else:
            cmd += ["-map", "0:s?"]

    # Video codec
    if options.video_codec:
        cmd += ["-c:v", options.video_codec]
    if options.resolution:
        cmd += ["-vf", f"scale={options.resolution.replace('x', ':')}"]
    if options.fps:
        cmd += ["-r", str(options.fps)]
    if options.video_bitrate:
        cmd += ["-b:v", options.video_bitrate]
    if options.crf is not None:
        cmd += ["-crf", str(options.crf)]

    # Audio codec
    if options.audio_codec:
        cmd += ["-c:a", options.audio_codec]
    if options.audio_bitrate:
        cmd += ["-b:a", options.audio_bitrate]

    # Subtitles
    if options.subtitle_mode == "embed_if_supported" and subtitles_supported:
        if target_ext == "mp4" or target_ext == "mov":
            cmd += ["-c:s", "mov_text"]
        else:
            cmd += ["-c:s", "copy"]
    elif options.subtitle_mode in ("drop",) or (
        options.subtitle_mode == "embed_if_supported" and not subtitles_supported
    ):
        cmd += ["-sn"]

    if options.preserve_chapters:
        cmd += ["-map_chapters", "0"]
    if options.preserve_metadata:
        cmd += ["-map_metadata", "0"]

    cmd += options.extra_args
    cmd += [str(output_path)]
    return cmd


def run_transcode(
    input_path: Path,
    output_path: Path,
    options: TranscodeOptions,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    timeout: int = 3600,
) -> Path:
    if not is_available():
        raise FfmpegError("FFmpeg was not found on PATH. Install FFmpeg to enable video/audio conversion.")

    media_probe: Optional[MediaProbe] = None
    total_duration = 0.0
    if ffprobe_available():
        try:
            media_probe = probe(input_path)
            total_duration = media_probe.duration_seconds
        except FfmpegError:
            pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_ffmpeg_command(input_path, output_path, options, media_probe)
    logger.info("Running FFmpeg: %s", " ".join(cmd))

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    stderr_lines: list[str] = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            stderr_lines.append(line)
            if cancel_check and cancel_check():
                proc.terminate()
                raise FfmpegError("Conversion cancelled by user.")

            dmatch = _DURATION_RE.search(line)
            if dmatch and total_duration == 0.0:
                h, m, s = dmatch.groups()
                total_duration = int(h) * 3600 + int(m) * 60 + float(s)

            tmatch = _TIME_RE.search(line)
            if tmatch and total_duration > 0 and progress_cb:
                h, m, s = tmatch.groups()
                current = int(h) * 3600 + int(m) * 60 + float(s)
                fraction = min(current / total_duration, 1.0)
                progress_cb(fraction, f"Encoding... {fraction * 100:.0f}%")

        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise FfmpegError(f"FFmpeg conversion timed out after {timeout}s.")

    if proc.returncode != 0:
        tail = "".join(stderr_lines[-25:])
        raise FfmpegError(f"FFmpeg exited with code {proc.returncode}:\n{tail}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise FfmpegError("FFmpeg reported success but produced no (or empty) output file.")

    return output_path


def validate_transcode_output(
    output_path: Path,
    source_probe: Optional[MediaProbe],
    options: TranscodeOptions,
) -> list[str]:
    issues: list[str] = []
    if not ffprobe_available():
        return issues
    try:
        out_probe = probe(output_path)
    except FfmpegError as exc:
        issues.append(f"Could not validate output media: {exc}")
        return issues

    if source_probe:
        if source_probe.video_streams and not out_probe.video_streams:
            issues.append("Source had video, but output has none.")
        if source_probe.audio_streams and not out_probe.audio_streams:
            issues.append("Source had audio, but output has none.")
        if (
            options.subtitle_mode == "embed_if_supported"
            and source_probe.subtitle_streams
            and not out_probe.subtitle_streams
        ):
            issues.append(
                "Source had subtitle tracks that could not be embedded in the "
                "target container and were dropped."
            )
        if source_probe.duration_seconds and out_probe.duration_seconds:
            drift = abs(source_probe.duration_seconds - out_probe.duration_seconds)
            if drift > max(2.0, source_probe.duration_seconds * 0.02):
                issues.append(
                    f"Output duration ({out_probe.duration_seconds:.1f}s) differs "
                    f"significantly from source ({source_probe.duration_seconds:.1f}s)."
                )
    return issues
