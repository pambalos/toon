"""Tests for TOON encoder."""

import math
import sys
from pathlib import Path

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from toon import EncodeOptions, encode


class TestPrimitives:
    """Test encoding of primitive values."""

    def test_null(self):
        assert encode(None) == "null"

    def test_true(self):
        assert encode(True) == "true"

    def test_false(self):
        assert encode(False) == "false"

    def test_integer(self):
        assert encode(42) == "42"
        assert encode(-17) == "-17"
        assert encode(0) == "0"

    def test_float(self):
        assert encode(3.14) == "3.14"
        assert encode(-2.5) == "-2.5"
        assert encode(0.0) == "0"

    def test_float_special_values(self):
        assert encode(float("nan")) == "null"
        assert encode(float("inf")) == "null"
        assert encode(float("-inf")) == "null"

    def test_simple_string(self):
        assert encode("hello") == "hello"

    def test_string_with_spaces(self):
        assert encode("hello world") == "hello world"

    def test_string_needs_quotes(self):
        # Contains colon
        assert encode("key: value") == '"key: value"'
        # Contains brackets
        assert encode("array[0]") == '"array[0]"'
        # Contains newline
        assert encode("line1\nline2") == '"line1\\nline2"'
        # Contains tab
        assert encode("col1\tcol2") == '"col1\\tcol2"'

    def test_reserved_literals(self):
        # These look like literals but should be quoted
        assert encode("true") == '"true"'
        assert encode("false") == '"false"'
        assert encode("null") == '"null"'

    def test_numeric_strings(self):
        # These look like numbers but should be quoted
        assert encode("123") == '"123"'
        assert encode("-45") == '"-45"'
        assert encode("3.14") == '"3.14"'

    def test_empty_string(self):
        assert encode("") == '""'


class TestObjects:
    """Test encoding of objects."""

    def test_empty_object(self):
        result = encode({})
        assert result == ""

    def test_simple_object(self):
        result = encode({"name": "Alice", "age": 30})
        assert "name: Alice" in result
        assert "age: 30" in result

    def test_nested_object(self):
        result = encode({"user": {"name": "Bob", "role": "admin"}})
        lines = result.split("\n")
        assert "user:" in lines[0]
        assert "  name: Bob" in lines[1]
        assert "  role: admin" in lines[2]

    def test_empty_nested_object(self):
        result = encode({"data": {}})
        assert result == "data:"

    def test_quoted_key(self):
        result = encode({"key with spaces": "value"})
        assert '"key with spaces": value' in result


class TestArraysInline:
    """Test inline primitive array encoding."""

    def test_string_array(self):
        result = encode({"tags": ["a", "b", "c"]})
        assert result == "tags[3]: a,b,c"

    def test_number_array(self):
        result = encode({"nums": [1, 2, 3]})
        assert result == "nums[3]: 1,2,3"

    def test_mixed_primitives(self):
        result = encode({"mix": [1, "two", True, None]})
        assert result == "mix[4]: 1,two,true,null"

    def test_empty_array(self):
        result = encode({"items": []})
        assert result == "items[0]:"


class TestArraysTabular:
    """Test tabular array encoding."""

    def test_simple_tabular(self):
        result = encode({"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]})
        lines = result.split("\n")
        assert lines[0] == "users[2]{id,name}:"
        assert lines[1] == "  1,Alice"
        assert lines[2] == "  2,Bob"

    def test_tabular_with_quoted_values(self):
        result = encode(
            {"data": [{"key": "a,b"}, {"key": "c,d"}]}
        )
        lines = result.split("\n")
        assert lines[0] == "data[2]{key}:"
        assert '"a,b"' in lines[1]
        assert '"c,d"' in lines[2]


class TestArraysList:
    """Test list format array encoding."""

    def test_nested_objects(self):
        result = encode({"items": [{"a": {"b": 1}}, {"a": {"b": 2}}]})
        lines = result.split("\n")
        assert "items[2]:" in lines[0]
        assert "- a:" in lines[1]

    def test_mixed_types(self):
        result = encode({"items": [1, {"x": 2}, "three"]})
        lines = result.split("\n")
        assert "items[3]:" in lines[0]
        assert "- 1" in lines[1]
        assert "- x: 2" in lines[2]
        assert "- three" in lines[3]


class TestRootArray:
    """Test root-level array encoding."""

    def test_root_inline(self):
        result = encode([1, 2, 3])
        assert result == "[3]: 1,2,3"

    def test_root_tabular(self):
        result = encode([{"a": 1}, {"a": 2}])
        lines = result.split("\n")
        assert lines[0] == "[2]{a}:"
        assert lines[1] == "  1"
        assert lines[2] == "  2"

    def test_root_list(self):
        result = encode([{"a": {"b": 1}}, {"a": {"b": 2}}])
        lines = result.split("\n")
        assert "[2]:" in lines[0]
        assert "- a:" in lines[1]


class TestEscapeSequences:
    """Test string escape sequence encoding (critical for multiline!)."""

    def test_newline_escape(self):
        result = encode({"content": "line1\nline2"})
        assert result == 'content: "line1\\nline2"'

    def test_tab_escape(self):
        result = encode({"content": "col1\tcol2"})
        assert result == 'content: "col1\\tcol2"'

    def test_carriage_return_escape(self):
        result = encode({"content": "line1\rline2"})
        assert result == 'content: "line1\\rline2"'

    def test_backslash_escape(self):
        result = encode({"path": "C:\\Users\\name"})
        assert result == 'path: "C:\\\\Users\\\\name"'

    def test_quote_escape(self):
        result = encode({"msg": 'He said "hello"'})
        assert result == 'msg: "He said \\"hello\\""'

    def test_multiple_escapes(self):
        result = encode({"text": 'Line 1\nLine 2\twith "quotes"'})
        assert result == 'text: "Line 1\\nLine 2\\twith \\"quotes\\""'

    def test_multiline_content(self):
        """The critical test - multiline strings must be properly escaped."""
        content = """def hello():
    print("Hello, World!")
    return True"""
        result = encode({"code": content})
        # Should be a single line with escaped newlines
        assert "\n" not in result.split(": ", 1)[1] or result.count("\n") == 0
        assert "\\n" in result


class TestKeyFolding:
    """Test key folding (dotted paths)."""

    def test_no_folding_by_default(self):
        result = encode({"a": {"b": {"c": 1}}})
        assert "a.b.c" not in result
        assert "a:" in result

    def test_safe_folding(self):
        result = encode({"a": {"b": {"c": 1}}}, EncodeOptions(key_folding="safe"))
        assert "a.b.c: 1" in result

    def test_folding_stops_at_multiple_keys(self):
        result = encode(
            {"a": {"b": 1, "c": 2}},
            EncodeOptions(key_folding="safe"),
        )
        assert "a:" in result
        assert "b: 1" in result
        assert "c: 2" in result


class TestDelimiters:
    """Test delimiter options."""

    def test_tab_delimiter(self):
        result = encode(
            {"items": [1, 2, 3]},
            EncodeOptions(delimiter="\t"),
        )
        assert "items[3\t]:" in result
        assert "\t" in result.split(": ", 1)[1]

    def test_pipe_delimiter(self):
        result = encode(
            {"items": [1, 2, 3]},
            EncodeOptions(delimiter="|"),
        )
        assert "items[3|]:" in result
        assert "1|2|3" in result


class TestIndentation:
    """Test indentation options."""

    def test_default_indent(self):
        result = encode({"a": {"b": 1}})
        assert "  b: 1" in result

    def test_custom_indent(self):
        result = encode({"a": {"b": 1}}, EncodeOptions(indent=4))
        assert "    b: 1" in result


class TestNormalization:
    """Test value normalization."""

    def test_tuple_to_list(self):
        result = encode({"items": (1, 2, 3)})
        assert "items[3]: 1,2,3" in result

    def test_set_to_list(self):
        # Sets are sorted by string representation
        result = encode({"items": {3, 1, 2}})
        assert "items[3]:" in result

    def test_datetime_to_isoformat(self):
        from datetime import datetime

        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = encode({"timestamp": dt})
        assert "2024-01-15T10:30:00" in result
