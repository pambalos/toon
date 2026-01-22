"""Type definitions for TOON encoder/decoder."""

from dataclasses import dataclass, field
from typing import Any, Literal

# JSON type aliases
JsonPrimitive = str | int | float | bool | None
JsonArray = list["JsonValue"]
JsonObject = dict[str, "JsonValue"]
JsonValue = JsonPrimitive | JsonArray | JsonObject

# Delimiter options
Delimiter = Literal[",", "\t", "|"]


@dataclass
class EncodeOptions:
    """Options for TOON encoding."""

    indent: int = 2
    """Number of spaces per indentation level."""

    delimiter: Delimiter = ","
    """Delimiter for inline arrays and tabular rows."""

    key_folding: Literal["none", "safe"] = "none"
    """Whether to fold single-key object chains into dotted paths."""

    flatten_depth: int | None = None
    """Maximum depth for key folding. None means unlimited."""


@dataclass
class DecodeOptions:
    """Options for TOON decoding."""

    strict: bool = False
    """Enable strict validation (count mismatches, blank lines, etc.)."""

    expand_paths: bool = False
    """Expand dotted keys into nested objects."""

    indent: int = 2
    """Expected indentation size (for strict mode validation)."""


@dataclass
class ParsedLine:
    """A parsed line with indentation info."""

    raw: str
    """Original line content."""

    content: str
    """Content after stripping indentation."""

    indent: int
    """Number of leading spaces."""

    depth: int
    """Indentation level (indent / indent_size)."""

    line_number: int
    """1-based line number."""


@dataclass
class ArrayHeaderInfo:
    """Parsed array header information."""

    length: int
    """Declared array length."""

    delimiter: Delimiter = ","
    """Delimiter for this array's values."""

    fields: list[str] = field(default_factory=list)
    """Field names for tabular format (empty for non-tabular)."""
