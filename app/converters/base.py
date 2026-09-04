"""Base class for the plugin-style converter architecture.

Every concrete converter (documents, ebooks, images, video, audio, ...)
subclasses ``BaseConverter`` and is registered with the global
``ConverterRegistry``. The GUI and the workers never talk to a specific
converter class directly — they always go through the registry, so new
format support can be added by writing a new converter and registering
it, without touching the GUI or worker code.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Callable, Optional

from app.models import CapabilityInfo, ConversionJob, ConversionResult


ProgressCallback = Callable[[float, str], None]
"""fraction complete in [0, 1], human-readable status message"""


class BaseConverter(abc.ABC):
    """Abstract converter plugin.

    Subclasses must implement :meth:`capabilities` and :meth:`convert`.
    ``name`` should be a short, stable, unique identifier used in logs and
    the plugin registry (e.g. ``"office_documents"``).
    """

    name: str = "base"

    @abc.abstractmethod
    def capabilities(self) -> list[CapabilityInfo]:
        """Return the list of (input formats -> output formats) capability
        declarations this converter provides. A converter may declare
        several ``CapabilityInfo`` entries if fidelity/limitations differ
        per format pair (e.g. DOCX->PDF is high fidelity, DOCX->TXT is
        lossy)."""
        raise NotImplementedError

    @abc.abstractmethod
    def convert(
        self,
        job: ConversionJob,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ConversionResult:
        """Perform the conversion described by ``job``.

        Implementations should:
        - call ``progress_cb(fraction, message)`` periodically if possible,
        - periodically call ``cancel_check()`` and raise
          :class:`ConversionCancelled` if it returns True,
        - never raise for "expected" failures (bad input, missing tool) —
          instead return a ``ConversionResult`` with ``success=False`` and
          a clear ``error_message``.
        """
        raise NotImplementedError

    def supports(self, input_format: str, output_format: str) -> Optional[CapabilityInfo]:
        input_format = input_format.lower().lstrip(".")
        output_format = output_format.lower().lstrip(".")
        for cap in self.capabilities():
            if input_format in cap.input_formats and output_format in cap.output_formats:
                return cap
        return None


class ConversionCancelled(Exception):
    """Raised internally by converters when ``cancel_check`` returns True."""


class ConverterRegistry:
    """Global registry of available converter plugins."""

    def __init__(self) -> None:
        self._converters: list[BaseConverter] = []

    def register(self, converter: BaseConverter) -> None:
        self._converters.append(converter)

    @property
    def converters(self) -> list[BaseConverter]:
        return list(self._converters)

    def find_capability(self, input_format: str, output_format: str) -> Optional[tuple[BaseConverter, CapabilityInfo]]:
        for conv in self._converters:
            cap = conv.supports(input_format, output_format)
            if cap:
                return conv, cap
        return None

    def all_capabilities(self) -> list[tuple[BaseConverter, CapabilityInfo]]:
        result = []
        for conv in self._converters:
            for cap in conv.capabilities():
                result.append((conv, cap))
        return result

    def possible_output_formats(self, input_format: str) -> set[str]:
        input_format = input_format.lower().lstrip(".")
        formats: set[str] = set()
        for conv in self._converters:
            for cap in conv.capabilities():
                if input_format in cap.input_formats:
                    formats |= cap.output_formats
        return formats

    def all_input_formats(self) -> set[str]:
        formats: set[str] = set()
        for conv in self._converters:
            for cap in conv.capabilities():
                formats |= cap.input_formats
        return formats


# Process-wide singleton. Converters register themselves into this at
# import time via app.converters.register_all().
registry = ConverterRegistry()
