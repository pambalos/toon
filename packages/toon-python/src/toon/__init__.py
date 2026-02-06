"""
TOON (Token-Oriented Object Notation) - Python Implementation

A token-efficient JSON alternative optimized for LLM tool calls.
Achieves ~40% token savings while maintaining full JSON data model compatibility.

Usage:
    import toon

    # Encode Python data to TOON
    data = {"name": "Alice", "age": 30}
    encoded = toon.encode(data)

    # Decode TOON to Python data
    decoded = toon.decode(encoded)

    # With options
    from toon import EncodeOptions, DecodeOptions

    encoded = toon.encode(data, EncodeOptions(indent=4, key_folding="safe"))
    decoded = toon.decode(text, DecodeOptions(strict=True, expand_paths=True))
"""

__version__ = "1.1.0"

from .decode import decode, decode_lines, decode_stream_async
from .encode import encode, encode_lines
from .types import DecodeOptions, EncodeOptions, JsonValue, MultilineStyle

__all__ = [
    # Version
    "__version__",
    # Main API
    "encode",
    "encode_lines",
    "decode",
    "decode_lines",
    "decode_stream_async",
    # Options
    "EncodeOptions",
    "DecodeOptions",
    # Types
    "JsonValue",
    "MultilineStyle",
]
