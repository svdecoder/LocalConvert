from pathlib import Path

import pytest

from app.converters.images import ImageConverter
from app.models import ConversionJob


@pytest.fixture()
def sample_png(tmp_path) -> Path:
    from PIL import Image

    path = tmp_path / "input.png"
    img = Image.new("RGBA", (40, 30), (255, 0, 0, 128))
    img.save(path)
    return path


def test_png_to_jpg_flattens_transparency(sample_png, tmp_path):
    from PIL import Image

    out_dir = tmp_path / "out"
    job = ConversionJob(input_path=sample_png, output_format="jpg", output_dir=out_dir)
    converter = ImageConverter()
    result = converter.convert(job)

    assert result.success
    assert result.output_path.exists()
    with Image.open(result.output_path) as img:
        assert img.mode == "RGB"
    assert any("transparency" in w.message.lower() for w in result.warnings)


def test_png_to_webp_preserves_transparency(sample_png, tmp_path):
    out_dir = tmp_path / "out"
    job = ConversionJob(input_path=sample_png, output_format="webp", output_dir=out_dir)
    converter = ImageConverter()
    result = converter.convert(job)

    assert result.success
    assert result.preserved.transparency is True


def test_resize_option_changes_dimensions(sample_png, tmp_path):
    from PIL import Image

    out_dir = tmp_path / "out"
    job = ConversionJob(
        input_path=sample_png, output_format="png", output_dir=out_dir,
        options={"resize_width": 20, "resize_height": 15},
    )
    converter = ImageConverter()
    result = converter.convert(job)
    assert result.success
    with Image.open(result.output_path) as img:
        assert img.size == (20, 15)


def test_does_not_overwrite_existing_output(sample_png, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "input.png").write_bytes(b"not a real png - sentinel")

    job = ConversionJob(input_path=sample_png, output_format="png", output_dir=out_dir)
    converter = ImageConverter()
    result = converter.convert(job)

    assert result.success
    assert result.output_path.name != "input.png"
    # Original sentinel file must remain untouched.
    assert (out_dir / "input.png").read_bytes() == b"not a real png - sentinel"


def test_capability_declared_for_svg_wrapping(sample_png, tmp_path):
    out_dir = tmp_path / "out"
    job = ConversionJob(input_path=sample_png, output_format="svg", output_dir=out_dir)
    converter = ImageConverter()
    result = converter.convert(job)
    assert result.success
    content = result.output_path.read_text(encoding="utf-8")
    assert content.startswith("<svg")
    assert any("not true vector" in w.message.lower() or "not a true vector" in w.message.lower() for w in result.warnings)
