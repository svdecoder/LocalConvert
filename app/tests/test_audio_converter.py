from pathlib import Path
from unittest.mock import patch

import pytest

from app.converters.audio import AudioConverter
from app.engines import ffmpeg_engine
from app.models import ConversionJob


@pytest.fixture()
def sample_audio(tmp_path) -> Path:
    path = tmp_path / "input.mp3"
    path.write_bytes(b"not a real mp3 - test fixture")
    return path


@pytest.fixture()
def sample_video(tmp_path) -> Path:
    path = tmp_path / "input.mp4"
    path.write_bytes(b"not a real video - test fixture")
    return path


def _fake_write_output(input_path, output_path, options, progress_cb=None, cancel_check=None, timeout=3600):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake audio output")
    return output_path


def test_audio_converter_missing_ffmpeg(sample_audio, tmp_path):
    with patch.object(ffmpeg_engine, "is_available", return_value=False):
        converter = AudioConverter()
        job = ConversionJob(input_path=sample_audio, output_format="flac", output_dir=tmp_path / "out")
        result = converter.convert(job)
    assert result.success is False
    assert "FFmpeg" in result.error_message


def test_audio_converter_lossy_to_lossless_warns(sample_audio, tmp_path):
    with patch.object(ffmpeg_engine, "is_available", return_value=True), \
         patch.object(ffmpeg_engine, "run_transcode", side_effect=_fake_write_output), \
         patch.object(ffmpeg_engine, "validate_transcode_output", return_value=[]):
        converter = AudioConverter()
        job = ConversionJob(input_path=sample_audio, output_format="flac", output_dir=tmp_path / "out")
        result = converter.convert(job)

    assert result.success
    assert any("already lossy" in w.message.lower() for w in result.warnings)


def test_audio_converter_extracts_from_video(sample_video, tmp_path):
    captured = {}

    def fake_run(input_path, output_path, options, progress_cb=None, cancel_check=None, timeout=3600):
        captured["options"] = options
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake audio")
        return output_path

    with patch.object(ffmpeg_engine, "is_available", return_value=True), \
         patch.object(ffmpeg_engine, "run_transcode", side_effect=fake_run), \
         patch.object(ffmpeg_engine, "validate_transcode_output", return_value=[]):
        converter = AudioConverter()
        job = ConversionJob(input_path=sample_video, output_format="mp3", output_dir=tmp_path / "out")
        result = converter.convert(job)

    assert result.success
    assert "-vn" in captured["options"].extra_args
    assert any("video file" in w.message.lower() for w in result.warnings)
