from pathlib import Path
from unittest.mock import patch

import pytest

from app.converters.video import VideoConverter
from app.engines import ffmpeg_engine
from app.models import ConversionJob


@pytest.fixture()
def sample_video(tmp_path) -> Path:
    path = tmp_path / "input.mkv"
    path.write_bytes(b"not a real video - test fixture")
    return path


def _fake_probe_with_subs(*_args, **_kwargs):
    return ffmpeg_engine.MediaProbe(
        duration_seconds=120.0,
        format_name="matroska",
        streams=[
            ffmpeg_engine.StreamInfo(index=0, codec_type="video", codec_name="h264"),
            ffmpeg_engine.StreamInfo(index=1, codec_type="audio", codec_name="aac"),
            ffmpeg_engine.StreamInfo(index=2, codec_type="subtitle", codec_name="subrip"),
        ],
        chapters=[],
        tags={},
    )


def test_video_converter_reports_missing_ffmpeg(sample_video, tmp_path):
    with patch.object(ffmpeg_engine, "is_available", return_value=False):
        converter = VideoConverter()
        job = ConversionJob(input_path=sample_video, output_format="mp4", output_dir=tmp_path / "out")
        result = converter.convert(job)
    assert result.success is False
    assert "FFmpeg" in result.error_message


def test_video_converter_warns_when_target_drops_subtitles(sample_video, tmp_path):
    out_dir = tmp_path / "out"

    def fake_run_transcode(input_path, output_path, options, progress_cb=None, cancel_check=None, timeout=3600):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake output")
        return output_path

    with patch.object(ffmpeg_engine, "is_available", return_value=True), \
         patch.object(ffmpeg_engine, "ffprobe_available", return_value=True), \
         patch.object(ffmpeg_engine, "probe", side_effect=_fake_probe_with_subs), \
         patch.object(ffmpeg_engine, "run_transcode", side_effect=fake_run_transcode), \
         patch.object(ffmpeg_engine, "validate_transcode_output", return_value=[]):
        converter = VideoConverter()
        # AVI does not support embedded subtitles per _SUBTITLE_CAPABLE_CONTAINERS
        job = ConversionJob(input_path=sample_video, output_format="avi", output_dir=out_dir)
        result = converter.convert(job)

    assert result.success
    assert any("subtitle" in w.message.lower() for w in result.warnings)


def test_video_converter_selects_default_codec_for_container(sample_video, tmp_path):
    out_dir = tmp_path / "out"
    captured = {}

    def fake_run_transcode(input_path, output_path, options, progress_cb=None, cancel_check=None, timeout=3600):
        captured["options"] = options
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake output")
        return output_path

    with patch.object(ffmpeg_engine, "is_available", return_value=True), \
         patch.object(ffmpeg_engine, "ffprobe_available", return_value=False), \
         patch.object(ffmpeg_engine, "run_transcode", side_effect=fake_run_transcode), \
         patch.object(ffmpeg_engine, "validate_transcode_output", return_value=[]):
        converter = VideoConverter()
        job = ConversionJob(input_path=sample_video, output_format="webm", output_dir=out_dir)
        result = converter.convert(job)

    assert result.success
    assert captured["options"].video_codec == "libvpx-vp9"
    assert captured["options"].audio_codec == "libopus"
