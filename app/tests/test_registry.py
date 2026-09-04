import pytest

from app.converters import register_all
from app.converters.base import ConverterRegistry
from app.converters.images import ImageConverter
from app.converters.video import VideoConverter


@pytest.fixture()
def full_registry():
    return register_all()


def test_register_all_populates_registry(full_registry):
    assert len(full_registry.converters) >= 6


def test_docx_to_pdf_is_supported(full_registry):
    found = full_registry.find_capability("docx", "pdf")
    assert found is not None
    converter, cap = found
    assert "pdf" in cap.output_formats
    assert "libreoffice" in cap.required_tools


def test_unsupported_pair_returns_none(full_registry):
    found = full_registry.find_capability("mp3", "docx")
    assert found is None


def test_possible_output_formats_for_png(full_registry):
    formats = full_registry.possible_output_formats("png")
    assert "jpg" in formats or "jpeg" in formats
    assert "webp" in formats


def test_image_converter_capabilities_declare_fidelity():
    conv = ImageConverter()
    caps = conv.capabilities()
    assert all(cap.fidelity is not None for cap in caps)
    raster_cap = next(c for c in caps if "png" in c.input_formats and "jpg" in c.output_formats)
    assert "py:PIL" in raster_cap.required_tools


def test_video_converter_declares_subtitle_limitation():
    conv = VideoConverter()
    caps = conv.capabilities()
    assert any("subtitle" in lim.lower() for cap in caps for lim in cap.limitations)


def test_registry_isolated_instance_independent():
    reg = ConverterRegistry()
    assert reg.converters == []
    reg.register(ImageConverter())
    assert len(reg.converters) == 1
