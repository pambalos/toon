"""Primitive value encoding and parsing for TOON."""

import math
from typing import TYPE_CHECKING

from .string_utils import escape_string, is_safe_unquoted, needs_quoting, unescape_string

if TYPE_CHECKING:
    from .types import Delimiter, JsonPrimitive


def encode_primitive(value: "JsonPrimitive", delimiter: "Delimiter" = ",") -> str:
    """
    Encode a primitive value to TOON format.

    Args:
        value: The primitive value (str, int, float, bool, or None).
        delimiter: The active delimiter for quoting checks.

    Returns:
        The encoded string representation.
    """
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return _encode_number(value)

    if isinstance(value, str):
        return encode_string_literal(value, delimiter)

    raise TypeError(f"Cannot encode value of type {type(value).__name__}")


def _encode_number(value: int | float) -> str:
    """Encode a number to TOON format."""
    # Handle special float values
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "null"
        # Normalize -0 to 0
        if value == 0.0:
            return "0"
        # Use repr for precise float representation
        s = repr(value)
        # Remove unnecessary .0 for whole numbers
        if s.endswith(".0") and "e" not in s.lower():
            return s[:-2]
        return s

    return str(value)


def encode_string_literal(value: str, delimiter: "Delimiter" = ",") -> str:
    """
    Encode a string value, with or without quotes.

    Args:
        value: The string to encode.
        delimiter: The active delimiter for quoting checks.

    Returns:
        The encoded string (quoted if necessary).
    """
    if is_safe_unquoted(value, delimiter):
        return value
    return f'"{escape_string(value)}"'


def encode_key(key: str) -> str:
    """
    Encode an object key for TOON format.

    Keys need quoting if they contain special characters or internal spaces.

    Args:
        key: The key string.

    Returns:
        The encoded key (quoted if necessary).
    """
    # Keys need quoting if they have special chars or internal spaces
    if not key:
        return '""'
    # Check for internal spaces (not just leading/trailing)
    if " " in key:
        return f'"{escape_string(key)}"'
    if is_safe_unquoted(key, ","):
        return key
    return f'"{escape_string(key)}"'


def parse_primitive(token: str) -> "JsonPrimitive":
    """
    Parse a primitive token to a Python value.

    Handles: null, true, false, numbers, quoted strings, unquoted strings.

    Args:
        token: The token string (trimmed).

    Returns:
        The parsed Python value.

    Raises:
        SyntaxError: For malformed quoted strings.
    """
    # Empty token is empty string
    if not token:
        return ""

    # Quoted string
    if token.startswith('"'):
        return parse_string_literal(token)

    # Literals
    if token == "null":
        return None
    if token == "true":
        return True
    if token == "false":
        return False

    # Try to parse as number
    number = _try_parse_number(token)
    if number is not None:
        return number

    # Unquoted string
    return token


def parse_string_literal(token: str) -> str:
    """
    Parse a quoted string literal.

    Args:
        token: The token starting with '"'.

    Returns:
        The unescaped string content.

    Raises:
        SyntaxError: If the string is malformed.
    """
    if not token.startswith('"'):
        raise SyntaxError(f"String literal must start with quote: {token}")

    # Find the closing quote
    end = find_closing_quote(token, 0)
    if end == -1:
        raise SyntaxError(f"Unterminated string: {token}")

    # Extract content between quotes
    content = token[1:end]
    return unescape_string(content)


def find_closing_quote(s: str, start: int) -> int:
    """
    Find the closing quote in a string.

    Args:
        s: The string to search.
        start: The position of the opening quote.

    Returns:
        Index of the closing quote, or -1 if not found.
    """
    i = start + 1
    while i < len(s):
        char = s[i]
        if char == "\\":
            # Skip escape sequence
            i += 2
            continue
        elif char == '"':
            return i
        i += 1
    return -1


def _try_parse_number(token: str) -> int | float | None:
    """
    Try to parse a token as a number.

    Returns None if it's not a valid number.
    """
    if not token:
        return None

    # Reject strings with leading zeros (they're strings, not numbers)
    # But allow "0", "0.5", "-0.5", etc.
    clean = token.lstrip("-")
    if len(clean) > 1 and clean[0] == "0" and clean[1].isdigit():
        return None

    try:
        # Try integer first
        if "." not in token and "e" not in token.lower():
            return int(token)

        # Try float
        value = float(token)

        # Normalize -0 to 0
        if value == 0.0:
            return 0

        return value
    except ValueError:
        return None


def format_array_header(
    length: int,
    key: str | None = None,
    fields: list[str] | None = None,
    delimiter: "Delimiter" = ",",
) -> str:
    """
    Format an array header line.

    Args:
        length: The array length.
        key: Optional key name (None for root arrays or list items).
        fields: Optional field names for tabular format.
        delimiter: The delimiter (included in bracket if not comma).

    Returns:
        The formatted header string.
    """
    # Build the bracket portion
    if delimiter == ",":
        bracket = f"[{length}]"
    else:
        bracket = f"[{length}{delimiter}]"

    # Build the fields portion
    fields_part = ""
    if fields:
        encoded_fields = [encode_key(f) for f in fields]
        fields_part = "{" + delimiter.join(encoded_fields) + "}"

    # Combine
    if key:
        return f"{encode_key(key)}{bracket}{fields_part}:"
    return f"{bracket}{fields_part}:"
