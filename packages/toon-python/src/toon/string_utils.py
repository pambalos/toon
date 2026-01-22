"""String utilities for TOON encoding/decoding."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import Delimiter

# TOON only allows these 5 escape sequences
ESCAPE_MAP = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}

UNESCAPE_MAP = {
    "\\": "\\",
    '"': '"',
    "n": "\n",
    "r": "\r",
    "t": "\t",
}

# Reserved literals that can't be unquoted strings
RESERVED_LITERALS = {"true", "false", "null"}

# Structural characters that require quoting
STRUCTURAL_CHARS = frozenset(":[]{}")

# Pattern for valid identifier segments (used in key folding/path expansion)
IDENTIFIER_SEGMENT_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def escape_string(value: str) -> str:
    """
    Escape a string for use in TOON quoted strings.

    Only the 5 valid TOON escape sequences are produced:
    - \\\\ (backslash)
    - \\" (double quote)
    - \\n (newline)
    - \\r (carriage return)
    - \\t (tab)

    Args:
        value: The string to escape.

    Returns:
        The escaped string (without surrounding quotes).
    """
    result = []
    for char in value:
        if char in ESCAPE_MAP:
            result.append(ESCAPE_MAP[char])
        else:
            result.append(char)
    return "".join(result)


def unescape_string(value: str) -> str:
    """
    Unescape a TOON string that was inside quotes.

    Processes the 5 valid escape sequences:
    - \\\\ → backslash
    - \\" → double quote
    - \\n → newline
    - \\r → carriage return
    - \\t → tab

    Args:
        value: The string content (without surrounding quotes).

    Returns:
        The unescaped string.

    Raises:
        SyntaxError: If an invalid escape sequence is found or backslash at end.
    """
    result = []
    i = 0
    while i < len(value):
        char = value[i]
        if char == "\\":
            if i + 1 >= len(value):
                raise SyntaxError("Backslash at end of string")
            next_char = value[i + 1]
            if next_char in UNESCAPE_MAP:
                result.append(UNESCAPE_MAP[next_char])
                i += 2
            else:
                raise SyntaxError(f"Invalid escape sequence: \\{next_char}")
        else:
            result.append(char)
            i += 1
    return "".join(result)


def is_safe_unquoted(value: str, delimiter: "Delimiter" = ",") -> bool:
    """
    Check if a string can be safely represented without quotes.

    A string can be unquoted if:
    - Non-empty
    - No leading/trailing whitespace
    - Not a boolean/null/number literal
    - No structural chars (: [ ] { })
    - No quotes or backslashes
    - No control chars (newline, carriage return, tab)
    - No active delimiter
    - Doesn't start with '-' (list marker)

    Args:
        value: The string to check.
        delimiter: The active delimiter character.

    Returns:
        True if the string can be unquoted.
    """
    if not value:
        return False

    # Check for leading/trailing whitespace
    if value != value.strip():
        return False

    # Check reserved literals
    if value.lower() in RESERVED_LITERALS:
        return False

    # Check if it looks like a number
    if _looks_like_number(value):
        return False

    # Check for structural characters
    if any(c in STRUCTURAL_CHARS for c in value):
        return False

    # Check for quotes and backslashes
    if '"' in value or "\\" in value:
        return False

    # Check for control characters
    if "\n" in value or "\r" in value or "\t" in value:
        return False

    # Check for delimiter
    if delimiter in value:
        return False

    # Can't start with list marker
    if value.startswith("-"):
        return False

    return True


def _looks_like_number(value: str) -> bool:
    """Check if a string looks like a number literal."""
    if not value:
        return False

    # Handle negative numbers
    s = value
    if s.startswith("-"):
        s = s[1:]
        if not s:
            return False

    # Check for leading zeros (strings like "007")
    if len(s) > 1 and s[0] == "0" and s[1].isdigit():
        return False

    # Try to parse as float
    try:
        float(value)
        return True
    except ValueError:
        return False


def needs_quoting(value: str, delimiter: "Delimiter" = ",") -> bool:
    """
    Check if a string needs to be quoted.

    Args:
        value: The string to check.
        delimiter: The active delimiter character.

    Returns:
        True if the string needs quotes.
    """
    return not is_safe_unquoted(value, delimiter)


def is_valid_identifier_segment(segment: str) -> bool:
    """
    Check if a string is a valid identifier segment for path expansion.

    Valid segments:
    - Start with letter or underscore
    - Only letters, digits, underscores

    Args:
        segment: The segment to check.

    Returns:
        True if valid identifier segment.
    """
    return bool(IDENTIFIER_SEGMENT_PATTERN.match(segment))


def is_valid_dotted_path(key: str) -> bool:
    """
    Check if a key is a valid dotted path for folding/expansion.

    Args:
        key: The key to check (may contain dots).

    Returns:
        True if all segments are valid identifiers.
    """
    if not key or "." not in key:
        return False
    segments = key.split(".")
    return all(is_valid_identifier_segment(seg) for seg in segments)


def find_unquoted_colon(line: str) -> int:
    """
    Find the position of the first unquoted colon in a line.

    Args:
        line: The line to search.

    Returns:
        Index of the colon, or -1 if not found.
    """
    in_quotes = False
    i = 0
    while i < len(line):
        char = line[i]
        if char == "\\" and in_quotes and i + 1 < len(line):
            # Skip escape sequence
            i += 2
            continue
        elif char == '"':
            in_quotes = not in_quotes
        elif char == ":" and not in_quotes:
            return i
        i += 1
    return -1


def split_by_delimiter(value: str, delimiter: "Delimiter") -> list[str]:
    """
    Split a string by delimiter, respecting quoted sections.

    Args:
        value: The string to split.
        delimiter: The delimiter character.

    Returns:
        List of values (still containing quotes if originally quoted).
    """
    result = []
    current = []
    in_quotes = False
    i = 0

    while i < len(value):
        char = value[i]
        if char == "\\" and in_quotes and i + 1 < len(value):
            # Keep escape sequence intact
            current.append(char)
            current.append(value[i + 1])
            i += 2
            continue
        elif char == '"':
            in_quotes = not in_quotes
            current.append(char)
        elif char == delimiter and not in_quotes:
            result.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        i += 1

    # Add the last segment
    result.append("".join(current).strip())
    return result
