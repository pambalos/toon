"""TOON encoder implementation."""

from collections.abc import Generator
from typing import Any

from .primitives import encode_key, encode_primitive, format_array_header
from .string_utils import is_valid_identifier_segment
from .types import Delimiter, EncodeOptions, JsonValue


def encode(value: Any, options: EncodeOptions | None = None) -> str:
    """
    Encode a Python value to TOON format.

    Args:
        value: The value to encode (dict, list, or primitive).
        options: Encoding options.

    Returns:
        The TOON-formatted string.
    """
    opts = options or EncodeOptions()
    lines = list(encode_lines(value, opts))
    return "\n".join(lines)


def encode_lines(
    value: Any, options: EncodeOptions | None = None
) -> Generator[str, None, None]:
    """
    Encode a Python value to TOON format, yielding lines.

    This is memory-efficient for large data structures.

    Args:
        value: The value to encode.
        options: Encoding options.

    Yields:
        Lines of TOON output.
    """
    opts = options or EncodeOptions()
    normalized = _normalize_value(value)

    # Root form detection
    if isinstance(normalized, dict):
        # Root object
        yield from _encode_object_lines(normalized, opts, 0, set())
    elif isinstance(normalized, list):
        # Root array
        yield from _encode_root_array(normalized, opts)
    else:
        # Root primitive
        yield encode_primitive(normalized, opts.delimiter)


def _encode_root_array(arr: list, opts: EncodeOptions) -> Generator[str, None, None]:
    """Encode a root-level array."""
    # Detect best format
    if _is_inline_primitive_array(arr):
        # Inline primitive array
        values = [encode_primitive(v, opts.delimiter) for v in arr]
        bracket = _format_bracket(len(arr), opts.delimiter)
        yield f"{bracket}: " + opts.delimiter.join(values)
    elif _is_tabular_array(arr):
        # Tabular format
        fields = list(arr[0].keys())
        yield format_array_header(len(arr), key=None, fields=fields, delimiter=opts.delimiter)
        for row in arr:
            yield from _encode_tabular_row(row, fields, opts, 1)
    else:
        # List format
        bracket = _format_bracket(len(arr), opts.delimiter)
        yield f"{bracket}:"
        for item in arr:
            yield from _encode_list_item(item, opts, 1)


def _encode_object_lines(
    obj: dict,
    opts: EncodeOptions,
    depth: int,
    sibling_keys: set[str],
) -> Generator[str, None, None]:
    """Encode an object's key-value pairs."""
    indent = " " * (opts.indent * depth)

    for key, value in obj.items():
        normalized = _normalize_value(value)

        # Try key folding
        if opts.key_folding == "safe" and _can_fold_key(key, normalized, sibling_keys, opts, depth):
            yield from _encode_folded(key, normalized, opts, depth, sibling_keys)
            continue

        encoded_key = encode_key(key)

        if isinstance(normalized, dict):
            if not normalized:
                # Empty object
                yield f"{indent}{encoded_key}:"
            else:
                # Nested object
                yield f"{indent}{encoded_key}:"
                yield from _encode_object_lines(normalized, opts, depth + 1, set())
        elif isinstance(normalized, list):
            yield from _encode_array(key, normalized, opts, depth)
        else:
            # Primitive value
            encoded_value = encode_primitive(normalized, opts.delimiter)
            yield f"{indent}{encoded_key}: {encoded_value}"


def _encode_array(
    key: str, arr: list, opts: EncodeOptions, depth: int
) -> Generator[str, None, None]:
    """Encode an array with the best format."""
    indent = " " * (opts.indent * depth)
    encoded_key = encode_key(key)

    if not arr:
        # Empty array
        bracket = _format_bracket(0, opts.delimiter)
        yield f"{indent}{encoded_key}{bracket}:"
    elif _is_inline_primitive_array(arr):
        # Inline primitive array
        values = [encode_primitive(v, opts.delimiter) for v in arr]
        bracket = _format_bracket(len(arr), opts.delimiter)
        yield f"{indent}{encoded_key}{bracket}: " + opts.delimiter.join(values)
    elif _is_tabular_array(arr):
        # Tabular format
        fields = list(arr[0].keys())
        header = format_array_header(len(arr), key=key, fields=fields, delimiter=opts.delimiter)
        yield f"{indent}{header}"
        for row in arr:
            yield from _encode_tabular_row(row, fields, opts, depth + 1)
    else:
        # List format
        bracket = _format_bracket(len(arr), opts.delimiter)
        yield f"{indent}{encoded_key}{bracket}:"
        for item in arr:
            yield from _encode_list_item(item, opts, depth + 1)


def _encode_list_item(
    item: JsonValue, opts: EncodeOptions, depth: int
) -> Generator[str, None, None]:
    """Encode a list item (after the - marker)."""
    indent = " " * (opts.indent * depth)
    normalized = _normalize_value(item)

    if isinstance(normalized, dict):
        if not normalized:
            # Empty object as list item
            yield f"{indent}-"
        else:
            # Check for tabular-first pattern
            first_key = next(iter(normalized.keys()))
            first_value = _normalize_value(normalized[first_key])

            if isinstance(first_value, list) and _is_tabular_array(first_value):
                # Tabular-first list item pattern
                yield from _encode_tabular_first_list_item(normalized, opts, depth)
            else:
                # Regular object as list item - put first field on hyphen line
                yield from _encode_object_list_item(normalized, opts, depth)
    elif isinstance(normalized, list):
        # Nested array as list item
        if _is_inline_primitive_array(normalized):
            values = [encode_primitive(v, opts.delimiter) for v in normalized]
            yield f"{indent}- [{len(normalized)}]: " + opts.delimiter.join(values)
        else:
            yield f"{indent}- [{len(normalized)}]:"
            for sub_item in normalized:
                yield from _encode_list_item(sub_item, opts, depth + 1)
    else:
        # Primitive as list item
        encoded = encode_primitive(normalized, opts.delimiter)
        yield f"{indent}- {encoded}"


def _encode_object_list_item(
    obj: dict, opts: EncodeOptions, depth: int
) -> Generator[str, None, None]:
    """Encode an object as a list item with first field on hyphen line."""
    indent = " " * (opts.indent * depth)
    child_indent = " " * (opts.indent * (depth + 1))

    items = list(obj.items())
    first_key, first_value = items[0]
    first_normalized = _normalize_value(first_value)

    encoded_key = encode_key(first_key)

    if isinstance(first_normalized, dict):
        if not first_normalized:
            yield f"{indent}- {encoded_key}:"
        else:
            yield f"{indent}- {encoded_key}:"
            yield from _encode_object_lines(first_normalized, opts, depth + 2, set())
    elif isinstance(first_normalized, list):
        # Array as first field of list item
        yield from _encode_list_item_array_first(first_key, first_normalized, opts, depth)
        # Remaining fields
        for key, value in items[1:]:
            normalized = _normalize_value(value)
            encoded_key = encode_key(key)
            if isinstance(normalized, dict):
                if not normalized:
                    yield f"{child_indent}{encoded_key}:"
                else:
                    yield f"{child_indent}{encoded_key}:"
                    yield from _encode_object_lines(normalized, opts, depth + 2, set())
            elif isinstance(normalized, list):
                yield from _encode_array(key, normalized, opts, depth + 1)
            else:
                yield f"{child_indent}{encoded_key}: {encode_primitive(normalized, opts.delimiter)}"
        return
    else:
        yield f"{indent}- {encoded_key}: {encode_primitive(first_normalized, opts.delimiter)}"

    # Remaining fields at depth + 1
    for key, value in items[1:]:
        normalized = _normalize_value(value)
        encoded_key = encode_key(key)
        if isinstance(normalized, dict):
            if not normalized:
                yield f"{child_indent}{encoded_key}:"
            else:
                yield f"{child_indent}{encoded_key}:"
                yield from _encode_object_lines(normalized, opts, depth + 2, set())
        elif isinstance(normalized, list):
            yield from _encode_array(key, normalized, opts, depth + 1)
        else:
            yield f"{child_indent}{encoded_key}: {encode_primitive(normalized, opts.delimiter)}"


def _encode_list_item_array_first(
    key: str, arr: list, opts: EncodeOptions, depth: int
) -> Generator[str, None, None]:
    """Encode a list item where first field is an array."""
    indent = " " * (opts.indent * depth)
    encoded_key = encode_key(key)

    if not arr:
        yield f"{indent}- {encoded_key}[0]:"
    elif _is_inline_primitive_array(arr):
        values = [encode_primitive(v, opts.delimiter) for v in arr]
        yield f"{indent}- {encoded_key}[{len(arr)}]: " + opts.delimiter.join(values)
    elif _is_tabular_array(arr):
        fields = list(arr[0].keys())
        header = format_array_header(len(arr), key=key, fields=fields, delimiter=opts.delimiter)
        yield f"{indent}- {header}"
        for row in arr:
            yield from _encode_tabular_row(row, fields, opts, depth + 2)
    else:
        yield f"{indent}- {encoded_key}[{len(arr)}]:"
        for item in arr:
            yield from _encode_list_item(item, opts, depth + 2)


def _encode_tabular_first_list_item(
    obj: dict, opts: EncodeOptions, depth: int
) -> Generator[str, None, None]:
    """Encode a list item with tabular array as first field."""
    indent = " " * (opts.indent * depth)
    child_indent = " " * (opts.indent * (depth + 1))

    items = list(obj.items())
    first_key, first_value = items[0]
    first_arr = _normalize_value(first_value)

    # First field is tabular array - put header on hyphen line
    fields = list(first_arr[0].keys())
    header = format_array_header(len(first_arr), key=first_key, fields=fields, delimiter=opts.delimiter)
    yield f"{indent}- {header}"

    # Tabular rows at depth + 2
    for row in first_arr:
        yield from _encode_tabular_row(row, fields, opts, depth + 2)

    # Remaining fields at depth + 1
    for key, value in items[1:]:
        normalized = _normalize_value(value)
        encoded_key = encode_key(key)
        if isinstance(normalized, dict):
            if not normalized:
                yield f"{child_indent}{encoded_key}:"
            else:
                yield f"{child_indent}{encoded_key}:"
                yield from _encode_object_lines(normalized, opts, depth + 2, set())
        elif isinstance(normalized, list):
            yield from _encode_array(key, normalized, opts, depth + 1)
        else:
            yield f"{child_indent}{encoded_key}: {encode_primitive(normalized, opts.delimiter)}"


def _encode_tabular_row(
    row: dict, fields: list[str], opts: EncodeOptions, depth: int
) -> Generator[str, None, None]:
    """Encode a single tabular row."""
    indent = " " * (opts.indent * depth)
    values = [encode_primitive(_normalize_value(row.get(f)), opts.delimiter) for f in fields]
    yield indent + opts.delimiter.join(values)


def _encode_folded(
    key: str,
    value: JsonValue,
    opts: EncodeOptions,
    depth: int,
    sibling_keys: set[str],
) -> Generator[str, None, None]:
    """Encode with key folding (dotted paths)."""
    indent = " " * (opts.indent * depth)

    # Build the path by walking down single-key objects
    path = [key]
    current = value

    max_depth = opts.flatten_depth if opts.flatten_depth is not None else float("inf")

    while (
        isinstance(current, dict)
        and len(current) == 1
        and len(path) <= max_depth
    ):
        next_key = next(iter(current.keys()))
        next_value = _normalize_value(current[next_key])

        # Check if we can continue folding
        if not is_valid_identifier_segment(next_key):
            break

        path.append(next_key)
        current = next_value

    folded_key = ".".join(path)

    if isinstance(current, dict):
        if not current:
            yield f"{indent}{folded_key}:"
        else:
            yield f"{indent}{folded_key}:"
            yield from _encode_object_lines(current, opts, depth + 1, set())
    elif isinstance(current, list):
        # Use the full folded key as the array key
        yield from _encode_array_with_key(folded_key, current, opts, depth)
    else:
        encoded_value = encode_primitive(current, opts.delimiter)
        yield f"{indent}{folded_key}: {encoded_value}"


def _format_bracket(length: int, delimiter: Delimiter) -> str:
    """Format the bracket portion of an array header."""
    if delimiter == ",":
        return f"[{length}]"
    return f"[{length}{delimiter}]"


def _encode_array_with_key(
    key: str, arr: list, opts: EncodeOptions, depth: int
) -> Generator[str, None, None]:
    """Encode an array with a pre-encoded key (for folded paths)."""
    indent = " " * (opts.indent * depth)

    if not arr:
        bracket = _format_bracket(0, opts.delimiter)
        yield f"{indent}{key}{bracket}:"
    elif _is_inline_primitive_array(arr):
        values = [encode_primitive(v, opts.delimiter) for v in arr]
        bracket = _format_bracket(len(arr), opts.delimiter)
        yield f"{indent}{key}{bracket}: " + opts.delimiter.join(values)
    elif _is_tabular_array(arr):
        fields = list(arr[0].keys())
        header = _format_array_header_with_key(len(arr), key, fields, opts.delimiter)
        yield f"{indent}{header}"
        for row in arr:
            yield from _encode_tabular_row(row, fields, opts, depth + 1)
    else:
        bracket = _format_bracket(len(arr), opts.delimiter)
        yield f"{indent}{key}{bracket}:"
        for item in arr:
            yield from _encode_list_item(item, opts, depth + 1)


def _format_array_header_with_key(
    length: int, key: str, fields: list[str], delimiter: Delimiter
) -> str:
    """Format array header with pre-encoded key."""
    if delimiter == ",":
        bracket = f"[{length}]"
    else:
        bracket = f"[{length}{delimiter}]"

    fields_part = ""
    if fields:
        encoded_fields = [encode_key(f) for f in fields]
        fields_part = "{" + delimiter.join(encoded_fields) + "}"

    return f"{key}{bracket}{fields_part}:"


def _can_fold_key(
    key: str,
    value: JsonValue,
    sibling_keys: set[str],
    opts: EncodeOptions,
    depth: int,
) -> bool:
    """Check if a key can be folded (dotted path)."""
    if not is_valid_identifier_segment(key):
        return False

    if not isinstance(value, dict) or len(value) != 1:
        return False

    next_key = next(iter(value.keys()))
    if not is_valid_identifier_segment(next_key):
        return False

    # Check for collision with sibling keys
    folded_prefix = f"{key}."
    for sibling in sibling_keys:
        if sibling.startswith(folded_prefix) or sibling == key:
            return False

    return True


def _is_inline_primitive_array(arr: list) -> bool:
    """Check if array can use inline primitive format."""
    if not arr:
        return False
    return all(_is_primitive(v) for v in arr)


def _is_tabular_array(arr: list) -> bool:
    """Check if array can use tabular format."""
    if not arr:
        return False

    # All elements must be objects
    if not all(isinstance(v, dict) for v in arr):
        return False

    # All objects must have same keys
    first_keys = set(arr[0].keys())
    if not first_keys:
        return False

    for item in arr[1:]:
        if set(item.keys()) != first_keys:
            return False

    # All values must be primitives
    for item in arr:
        for v in item.values():
            if not _is_primitive(_normalize_value(v)):
                return False

    return True


def _is_primitive(value: JsonValue) -> bool:
    """Check if value is a primitive (not dict or list)."""
    return not isinstance(value, (dict, list))


def _normalize_value(value: Any) -> JsonValue:
    """
    Normalize a value for JSON compatibility.

    Converts:
    - Date objects to ISO strings
    - Sets to lists
    - Other iterables to lists
    - Objects with toJSON() methods

    Args:
        value: The value to normalize.

    Returns:
        A JSON-compatible value.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        # Handle special float values
        if isinstance(value, float):
            import math
            if math.isnan(value) or math.isinf(value):
                return None
            # Normalize -0 to 0
            if value == 0.0:
                return 0
        return value

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]

    if isinstance(value, set):
        return [_normalize_value(v) for v in sorted(value, key=str)]

    # Check for toJSON method (like datetime objects)
    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "__iter__"):
        return [_normalize_value(v) for v in value]

    # Last resort: string conversion
    return str(value)
