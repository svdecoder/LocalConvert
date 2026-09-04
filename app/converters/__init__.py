"""Converter plugin registration.

This is the single place that wires concrete converter implementations
into the global registry. Adding support for a new format family means:
  1. Write a new BaseConverter subclass in this package.
  2. Add one line to ``register_all()``.
No other file needs to change.
"""

from __future__ import annotations

from app.converters.audio import AudioConverter
from app.converters.base import BaseConverter, ConversionCancelled, ConverterRegistry, registry
from app.converters.documents import DocumentConverter, SpreadsheetConverter
from app.converters.ebooks import EbookConverter
from app.converters.images import ImageConverter
from app.converters.video import VideoConverter

_registered = False


def register_all() -> ConverterRegistry:
    global _registered
    if not _registered:
        registry.register(DocumentConverter())
        registry.register(SpreadsheetConverter())
        registry.register(EbookConverter())
        registry.register(ImageConverter())
        registry.register(VideoConverter())
        registry.register(AudioConverter())
        _registered = True
    return registry


__all__ = [
    "BaseConverter",
    "ConversionCancelled",
    "ConverterRegistry",
    "registry",
    "register_all",
]
