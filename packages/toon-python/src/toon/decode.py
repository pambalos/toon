"""TOON decoder implementation."""

from __future__ import annotations

import re
from collections.abc import AsyncIterable, Iterable
from typing import TYPE_CHECKING

from .primitives import parse_primitive
from .string_utils import (
    find_unquoted_colon,
    is_valid_identifier_segment,
    split_by_delimiter,
    unescape_string,
)
from .types import ArrayHeaderInfo, DecodeOptions, Delimiter, JsonValue, ParsedLine

if TYPE_CHECKING:
    from collections.abc import Generator

# Marker for keys that were quoted in source (used to skip path expansion)
QUOTED_KEY_MARKER = "\x00QUOTED\x00"

# Pattern for array header: key[N<delim?>]{fields}:
ARRAY_HEADER_PATTERN = re.compile(
    r"^(?P<key>(?:[^:\[\]{}\"]+|\"(?:[^\"\\]|\\.)*\")?)?"  # Optional key (possibly quoted)
    r"\[(?P<length>\d+)(?P<delim>[,\t|])?\]"  # [N<delim?>]
    r"(?:\{(?P<fields>[^}]*)\})?"  # Optional {fields}
    r":(?P<rest>.*)$"  # Colon and rest
)


def decode(text: str, options: DecodeOptions | None = None) -> JsonValue:
    """
    Decode TOON text to a Python value.

    Args:
        text: The TOON-formatted string.
        options: Decoding options.

    Returns:
        The decoded Python value.

    Raises:
        SyntaxError: For malformed input.
        ValueError: For strict mode violations.
    """
    opts = options or DecodeOptions()
    lines = text.split("\n")
    return decode_lines(lines, opts)


def decode_lines(lines: Iterable[str], options: DecodeOptions | None = None) -> JsonValue:
    """
    Decode TOON from pre-split lines.

    Args:
        lines: Iterable of line strings.
        options: Decoding options.

    Returns:
        The decoded Python value.
    """
    opts = options or DecodeOptions()
    parsed_lines = list(_parse_lines(lines, opts.indent, opts.strict))

    if not parsed_lines:
        return None

    cursor = _Cursor(parsed_lines, opts)
    result = _decode_root(cursor)

    if opts.expand_paths:
        result = _expand_paths(result, opts.strict)

    return result


async def decode_stream_async(
    lines: AsyncIterable[str], options: DecodeOptions | None = None
) -> JsonValue:
    """
    Decode TOON from an async iterable of lines.

    Args:
        lines: Async iterable of line strings.
        options: Decoding options.

    Returns:
        The decoded Python value.
    """
    opts = options or DecodeOptions()
    collected = []
    async for line in lines:
        collected.append(line)
    return decode_lines(collected, opts)


class _Cursor:
    """Cursor for iterating through parsed lines."""

    def __init__(self, lines: list[ParsedLine], options: DecodeOptions):
        self.lines = lines
        self.options = options
        self.pos = 0

    @property
    def mark_quoted(self) -> bool:
        """Whether to mark quoted keys (for path expansion)."""
        return self.options.expand_paths

    def peek(self) -> ParsedLine | None:
        """Look at current line without advancing."""
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            if line.content:  # Skip blank lines
                return line
            self.pos += 1
        return None

    def advance(self) -> ParsedLine | None:
        """Get current line and advance position."""
        line = self.peek()
        if line:
            self.pos += 1
        return line

    def peek_at_depth(self, depth: int) -> ParsedLine | None:
        """Peek at next line at specific depth."""
        line = self.peek()
        if line and line.depth == depth:
            return line
        return None


def _parse_lines(
    lines: Iterable[str], indent_size: int, strict: bool
) -> Generator[ParsedLine, None, None]:
    """Parse raw lines into ParsedLine objects."""
    for i, raw in enumerate(lines, start=1):
        # Count leading spaces
        stripped = raw.lstrip(" ")
        indent = len(raw) - len(stripped)

        # Strict mode: check for tabs in indentation
        if strict and "\t" in raw[:indent]:
            raise SyntaxError(f"Line {i}: Tab in indentation (use spaces)")

        # Strict mode: check indent is multiple of indent_size
        if strict and indent % indent_size != 0:
            raise SyntaxError(
                f"Line {i}: Indentation {indent} is not a multiple of {indent_size}"
            )

        depth = indent // indent_size
        content = stripped.rstrip()

        yield ParsedLine(
            raw=raw,
            content=content,
            indent=indent,
            depth=depth,
            line_number=i,
        )


def _decode_root(cursor: _Cursor) -> JsonValue:
    """Decode the root value."""
    line = cursor.peek()
    if not line:
        return None

    # Check for root array
    if line.content.startswith("["):
        return _decode_root_array(cursor)

    # Check if it's a single primitive (no key: value pattern)
    colon_pos = find_unquoted_colon(line.content)
    if colon_pos == -1:
        # Check if there are more lines at depth 0
        cursor.advance()
        next_line = cursor.peek_at_depth(0)
        if next_line is None:
            # Single primitive
            return parse_primitive(line.content)

        # Multiple lines without colons - error
        raise SyntaxError(f"Line {line.line_number}: Expected key:value or array header")

    # Root object
    return _decode_object(cursor, 0)


def _decode_root_array(cursor: _Cursor) -> list:
    """Decode a root-level array."""
    line = cursor.advance()
    header = _parse_array_header(line.content, ",")

    if header.fields:
        # Tabular array
        return _decode_tabular_rows(cursor, header, 1)
    elif line.content.rstrip(":").endswith("]"):
        # Check for inline values
        rest = line.content[line.content.index(":") + 1 :].strip()
        if rest:
            # Inline primitive array
            return _decode_inline_values(rest, header, cursor.options)
        else:
            # List array
            return _decode_list_items(cursor, header.length, 1, cursor.options)
    else:
        # Inline primitive array (values after colon)
        rest = line.content[line.content.index(":") + 1 :].strip()
        return _decode_inline_values(rest, header, cursor.options)


def _decode_object(cursor: _Cursor, depth: int) -> dict:
    """Decode an object at the given depth."""
    result = {}

    while True:
        line = cursor.peek_at_depth(depth)
        if not line:
            break

        cursor.advance()
        key, value = _decode_key_value(line, cursor, depth)
        result[key] = value

    return result


def _decode_key_value(
    line: ParsedLine, cursor: _Cursor, depth: int
) -> tuple[str, JsonValue]:
    """Decode a key: value pair from a line."""
    content = line.content

    # Check for array header pattern
    array_match = ARRAY_HEADER_PATTERN.match(content)
    if array_match:
        key = _parse_key(array_match.group("key") or "", cursor.mark_quoted)
        header = _parse_array_header_from_match(array_match)
        rest = array_match.group("rest").strip()

        if header.fields:
            # Tabular array
            value = _decode_tabular_rows(cursor, header, depth + 1)
        elif rest:
            # Inline primitive array
            value = _decode_inline_values(rest, header, cursor.options)
        else:
            # List array
            value = _decode_list_items(cursor, header.length, depth + 1, cursor.options)

        return key, value

    # Regular key: value
    colon_pos = find_unquoted_colon(content)
    if colon_pos == -1:
        raise SyntaxError(f"Line {line.line_number}: Expected colon in key:value")

    key_part = content[:colon_pos].strip()
    value_part = content[colon_pos + 1 :].strip()

    key = _parse_key(key_part, cursor.mark_quoted)

    if value_part:
        # Check for YAML-style block scalar indicators
        if value_part in ("|", ">", "|-", ">-", "|+", ">+"):
            value = _decode_block_scalar(cursor, depth, value_part)
        else:
            # Inline value - but check for implicit multi-line continuation
            # If following lines don't look like valid TOON, treat as multi-line content
            continuation = _collect_implicit_multiline(cursor, depth)
            if continuation:
                # Combine first line with continuation
                value = value_part + "\n" + continuation
            else:
                value = parse_primitive(value_part)
    else:
        # Check for nested content
        next_line = cursor.peek()
        if next_line and next_line.depth > depth:
            # Nested object
            value = _decode_object(cursor, depth + 1)
        else:
            # Empty object
            value = {}

    return key, value


def _collect_implicit_multiline(cursor: _Cursor, parent_depth: int) -> str | None:
    """
    Collect implicit multi-line content when LLM doesn't use | indicator.

    After an inline value like `content: # Heading`, check if subsequent lines
    are "orphaned" (not valid TOON key:value pairs). If so, collect them as
    multi-line continuation.

    Only activates when the first non-blank following line is clearly NOT
    valid TOON structure (e.g., markdown heading, plain text paragraph).

    Args:
        cursor: The line cursor (positioned after the inline value line).
        parent_depth: The depth of the key that had the inline value.

    Returns:
        The collected multi-line content, or None if no continuation found.
    """
    start_pos = cursor.pos

    # First, peek at the first non-blank line to decide if we should even
    # enter implicit multiline mode. If it looks like valid TOON, bail out.
    peek_pos = cursor.pos
    first_content_line = None
    while peek_pos < len(cursor.lines):
        line = cursor.lines[peek_pos]
        if line.content:  # Non-blank
            first_content_line = line
            break
        peek_pos += 1

    if first_content_line is None:
        # No more content - nothing to collect
        return None

    # Check if first content line looks like valid TOON structure
    content = first_content_line.content

    # If it starts with - followed by space or has key:, it's likely TOON
    if content.startswith("- ") or content == "-":
        return None  # TOON list item

    if content.startswith("[") and "]" in content:
        return None  # Array header

    colon_pos = find_unquoted_colon(content)
    if colon_pos > 0:
        key_part = content[:colon_pos].strip()
        # Check if it looks like a valid TOON key (identifier-like)
        # Valid bare keys: start with letter/underscore, no spaces
        # Quoted keys: start with "
        if key_part:
            if key_part.startswith('"'):
                # Quoted key - valid TOON
                if not key_part.startswith("#"):
                    return None
            elif (key_part[0].isalpha() or key_part[0] == '_') and " " not in key_part:
                # Bare key without spaces - valid TOON (unless markdown heading)
                if not key_part.startswith("#"):
                    return None

    # OK, first line doesn't look like TOON - enter implicit multiline mode
    lines: list[str] = []

    while cursor.pos < len(cursor.lines):
        line = cursor.lines[cursor.pos]
        content = line.content

        # Empty/blank line - include in multi-line content
        if not content:
            cursor.pos += 1
            lines.append("")
            continue

        # Stop on lines that look like ACTUAL TOON sibling/parent keys
        if line.depth <= parent_depth:
            colon_pos = find_unquoted_colon(content)

            if colon_pos > 0:
                key_part = content[:colon_pos].strip()
                # Valid TOON key: starts with letter/underscore (no spaces), or quoted
                # But NOT markdown headings like "## Section:"
                if key_part and not key_part.startswith("#"):
                    if key_part.startswith('"'):
                        break  # Quoted key
                    elif (key_part[0].isalpha() or key_part[0] == '_') and " " not in key_part:
                        break  # Valid bare key

            if content.startswith("[") and "]:" in content:
                break

        # This line is content continuation
        cursor.pos += 1
        lines.append(line.raw.rstrip("\r\n"))

    # If we didn't collect anything meaningful, restore position
    if not lines or all(not l for l in lines):
        cursor.pos = start_pos
        return None

    # Strip trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        cursor.pos = start_pos
        return None

    return "\n".join(lines)


def _decode_block_scalar(cursor: _Cursor, depth: int, indicator: str) -> str:
    """
    Decode a YAML-style block scalar (literal | or folded >).

    Supports:
    - | (literal): preserves newlines
    - > (folded): folds newlines into spaces
    - |- or >- (strip): removes trailing newlines
    - |+ or >+ (keep): preserves trailing newlines

    Args:
        cursor: The line cursor.
        depth: The current indentation depth.
        indicator: The block scalar indicator (|, >, |-, >-, |+, >+).

    Returns:
        The decoded multi-line string.
    """
    content_lines: list[str] = []
    block_indent: int | None = None

    # Determine the style
    is_literal = indicator.startswith("|")  # | preserves newlines, > folds them
    chomping = "clip"  # default: single trailing newline
    if indicator.endswith("-"):
        chomping = "strip"  # no trailing newline
    elif indicator.endswith("+"):
        chomping = "keep"  # preserve all trailing newlines

    # Calculate minimum required indent (must be greater than parent depth)
    min_indent = (depth + 1) * cursor.options.indent

    # Access lines directly to not skip blank lines (cursor.peek() skips them)
    while cursor.pos < len(cursor.lines):
        line = cursor.lines[cursor.pos]
        raw = line.raw
        stripped = raw.lstrip(" ")
        current_indent = len(raw) - len(stripped)
        is_blank = not stripped.strip()

        # First non-blank line establishes the block indent
        if block_indent is None:
            if is_blank:
                # Blank line before content - preserve it
                cursor.pos += 1
                content_lines.append("")
                continue

            # First non-blank line must be indented more than parent
            if current_indent < min_indent:
                break

            block_indent = current_indent

        # Check if this line is still part of the block
        if is_blank:
            # Blank lines are always included (may be trimmed later by chomping)
            cursor.pos += 1
            content_lines.append("")
            continue

        # Non-blank line: check indent
        if current_indent < block_indent:
            # Less indented non-blank line ends the block
            break

        cursor.pos += 1

        # Remove the block indent from the line content
        content = raw[block_indent:].rstrip("\r\n")
        content_lines.append(content)

    # Handle trailing empty lines based on chomping indicator
    if chomping == "strip":
        # Remove all trailing empty lines
        while content_lines and not content_lines[-1]:
            content_lines.pop()
    elif chomping == "clip":
        # Keep at most one trailing newline (handled by join)
        while len(content_lines) > 1 and not content_lines[-1]:
            content_lines.pop()
    # "keep" preserves all trailing empty lines as-is

    # Join lines based on style
    if is_literal:
        # Literal style: preserve newlines exactly
        result = "\n".join(content_lines)
    else:
        # Folded style: fold single newlines into spaces, preserve double+ newlines
        result_parts = []
        current_paragraph: list[str] = []

        for line in content_lines:
            if not line:
                # Empty line = paragraph break
                if current_paragraph:
                    result_parts.append(" ".join(current_paragraph))
                    current_paragraph = []
                result_parts.append("")
            else:
                current_paragraph.append(line)

        if current_paragraph:
            result_parts.append(" ".join(current_paragraph))

        result = "\n".join(result_parts)

    # Add trailing newline for clip/keep modes if there's content
    if result and chomping in ("clip", "keep"):
        result += "\n"

    return result


def _decode_list_items(
    cursor: _Cursor, expected_length: int, depth: int, options: DecodeOptions
) -> list:
    """Decode list items (lines starting with -)."""
    result = []

    while len(result) < expected_length:
        line = cursor.peek_at_depth(depth)
        if not line:
            break

        if not line.content.startswith("- ") and line.content != "-":
            break

        cursor.advance()
        item = _decode_list_item(line, cursor, depth)
        result.append(item)

    if options.strict and len(result) != expected_length:
        raise ValueError(
            f"Array length mismatch: expected {expected_length}, got {len(result)}"
        )

    return result


def _decode_list_item(line: ParsedLine, cursor: _Cursor, depth: int) -> JsonValue:
    """Decode a single list item."""
    content = line.content

    if content == "-":
        # Bare hyphen - check for nested content
        next_line = cursor.peek()
        if next_line and next_line.depth > depth:
            return _decode_object(cursor, depth + 1)
        return {}

    # Remove "- " prefix
    item_content = content[2:].strip()

    if not item_content:
        # Empty - check for nested content
        next_line = cursor.peek()
        if next_line and next_line.depth > depth:
            return _decode_object(cursor, depth + 1)
        return {}

    # Check for array header on hyphen line
    array_match = ARRAY_HEADER_PATTERN.match(item_content)
    if array_match:
        return _decode_list_item_array(array_match, cursor, depth)

    # Check for key: value on hyphen line
    colon_pos = find_unquoted_colon(item_content)
    if colon_pos != -1:
        # Object with first field on hyphen line
        return _decode_list_item_object(item_content, colon_pos, cursor, depth)

    # Primitive value
    return parse_primitive(item_content)


def _decode_list_item_array(
    match: re.Match, cursor: _Cursor, depth: int
) -> dict | list:
    """Decode a list item that starts with an array header."""
    key = _parse_key(match.group("key") or "", cursor.mark_quoted)
    header = _parse_array_header_from_match(match)
    rest = match.group("rest").strip()

    if header.fields:
        # Tabular array
        arr = _decode_tabular_rows(cursor, header, depth + 2)
    elif rest:
        # Inline primitive array
        arr = _decode_inline_values(rest, header, cursor.options)
    else:
        # List array
        arr = _decode_list_items(cursor, header.length, depth + 2, cursor.options)

    if key:
        # This is an object with array as first field
        result = {key: arr}
        # Check for more fields at depth + 1
        while True:
            next_line = cursor.peek_at_depth(depth + 1)
            if not next_line:
                break
            cursor.advance()
            k, v = _decode_key_value(next_line, cursor, depth + 1)
            result[k] = v
        return result
    else:
        # Bare array as list item
        return arr


def _decode_list_item_object(
    item_content: str, colon_pos: int, cursor: _Cursor, depth: int
) -> dict:
    """Decode a list item that's an object with first field on hyphen line."""
    key_part = item_content[:colon_pos].strip()
    value_part = item_content[colon_pos + 1 :].strip()

    # Check if value_part is an array header
    if value_part and value_part.startswith("["):
        # Reconstruct full line for parsing
        full_content = key_part + value_part
        array_match = ARRAY_HEADER_PATTERN.match(full_content)
        if array_match:
            return _decode_list_item_array(array_match, cursor, depth)

    key = _parse_key(key_part, cursor.mark_quoted)

    if value_part:
        value = parse_primitive(value_part)
    else:
        # Check for nested content at depth + 2
        next_line = cursor.peek()
        if next_line and next_line.depth > depth + 1:
            value = _decode_object(cursor, depth + 2)
        else:
            value = {}

    result = {key: value}

    # Check for more fields at depth + 1
    while True:
        next_line = cursor.peek_at_depth(depth + 1)
        if not next_line:
            break
        cursor.advance()
        k, v = _decode_key_value(next_line, cursor, depth + 1)
        result[k] = v

    return result


def _decode_tabular_rows(
    cursor: _Cursor, header: ArrayHeaderInfo, depth: int
) -> list[dict]:
    """Decode tabular array rows."""
    result = []
    fields = header.fields

    while len(result) < header.length:
        line = cursor.peek_at_depth(depth)
        if not line:
            break

        cursor.advance()
        values = split_by_delimiter(line.content, header.delimiter)

        if len(values) != len(fields):
            if cursor.options.strict:
                raise ValueError(
                    f"Line {line.line_number}: Expected {len(fields)} values, got {len(values)}"
                )
            # Pad or truncate
            while len(values) < len(fields):
                values.append("")
            values = values[: len(fields)]

        row = {}
        for field, value in zip(fields, values):
            row[field] = parse_primitive(value)
        result.append(row)

    if cursor.options.strict and len(result) != header.length:
        raise ValueError(
            f"Tabular array length mismatch: expected {header.length}, got {len(result)}"
        )

    return result


def _decode_inline_values(
    values_str: str, header: ArrayHeaderInfo, options: DecodeOptions
) -> list:
    """Decode inline primitive array values."""
    if not values_str:
        if options.strict and header.length > 0:
            raise ValueError(f"Expected {header.length} inline values, got 0")
        return []

    values = split_by_delimiter(values_str, header.delimiter)
    result = [parse_primitive(v) for v in values]

    if options.strict and len(result) != header.length:
        raise ValueError(
            f"Inline array length mismatch: expected {header.length}, got {len(result)}"
        )

    return result


def _parse_array_header(content: str, default_delimiter: Delimiter) -> ArrayHeaderInfo:
    """Parse an array header line."""
    match = ARRAY_HEADER_PATTERN.match(content)
    if not match:
        raise SyntaxError(f"Invalid array header: {content}")
    return _parse_array_header_from_match(match, default_delimiter)


def _parse_array_header_from_match(
    match: re.Match, default_delimiter: Delimiter = ","
) -> ArrayHeaderInfo:
    """Parse ArrayHeaderInfo from a regex match."""
    length = int(match.group("length"))
    delimiter = match.group("delim") or default_delimiter

    fields_str = match.group("fields")
    if fields_str:
        fields = [_parse_key(f.strip()) for f in split_by_delimiter(fields_str, delimiter)]
    else:
        fields = []

    return ArrayHeaderInfo(length=length, delimiter=delimiter, fields=fields)


def _parse_key(key: str, mark_quoted: bool = False) -> str:
    """Parse a key, handling quoted keys.

    Args:
        key: The key string (possibly quoted).
        mark_quoted: If True, prefix quoted keys with QUOTED_KEY_MARKER.

    Returns:
        The parsed key, possibly with marker prefix.
    """
    key = key.strip()
    if not key:
        return ""
    if key.startswith('"') and key.endswith('"'):
        parsed = unescape_string(key[1:-1])
        if mark_quoted:
            return QUOTED_KEY_MARKER + parsed
        return parsed
    return key


def _strip_markers(value: JsonValue) -> JsonValue:
    """Strip QUOTED_KEY_MARKER from all keys in the value."""
    if isinstance(value, dict):
        return {
            k.removeprefix(QUOTED_KEY_MARKER): _strip_markers(v)
            for k, v in value.items()
        }
    elif isinstance(value, list):
        return [_strip_markers(v) for v in value]
    return value


def _expand_paths(value: JsonValue, strict: bool) -> JsonValue:
    """
    Expand dotted keys into nested objects.

    Args:
        value: The value to expand.
        strict: Whether to raise on conflicts.

    Returns:
        The expanded value.
    """
    if isinstance(value, dict):
        result = {}
        for key, val in value.items():
            expanded_val = _expand_paths(val, strict)

            # Check if key was quoted (marked) - skip expansion for quoted keys
            if key.startswith(QUOTED_KEY_MARKER):
                actual_key = key.removeprefix(QUOTED_KEY_MARKER)
                if actual_key in result:
                    if strict:
                        raise TypeError(f"Path expansion conflict for key: {actual_key}")
                    result[actual_key] = _merge_values(result[actual_key], expanded_val, strict)
                else:
                    result[actual_key] = expanded_val
            elif "." in key and _is_expandable_path(key):
                _set_nested(result, key.split("."), expanded_val, strict)
            else:
                if key in result:
                    if strict:
                        raise TypeError(f"Path expansion conflict for key: {key}")
                    result[key] = _merge_values(result[key], expanded_val, strict)
                else:
                    result[key] = expanded_val
        return result
    elif isinstance(value, list):
        return [_expand_paths(v, strict) for v in value]
    else:
        return value


def _is_expandable_path(key: str) -> bool:
    """Check if a key should be expanded as a dotted path."""
    segments = key.split(".")
    return all(is_valid_identifier_segment(seg) for seg in segments)


def _set_nested(obj: dict, path: list[str], value: JsonValue, strict: bool) -> None:
    """Set a value at a nested path, creating intermediate objects."""
    for i, segment in enumerate(path[:-1]):
        if segment not in obj:
            obj[segment] = {}
        elif not isinstance(obj[segment], dict):
            if strict:
                raise TypeError(f"Path expansion conflict: {'.'.join(path[:i+1])} is not an object")
            obj[segment] = {}
        obj = obj[segment]

    final_key = path[-1]
    if final_key in obj:
        if strict:
            raise TypeError(f"Path expansion conflict for key: {'.'.join(path)}")
        obj[final_key] = _merge_values(obj[final_key], value, strict)
    else:
        obj[final_key] = value


def _merge_values(existing: JsonValue, new: JsonValue, strict: bool) -> JsonValue:
    """Merge two values during path expansion."""
    if isinstance(existing, dict) and isinstance(new, dict):
        result = dict(existing)
        for key, val in new.items():
            if key in result:
                result[key] = _merge_values(result[key], val, strict)
            else:
                result[key] = val
        return result
    # Non-dict values: new wins
    return new
