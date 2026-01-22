"""Tests for TOON decoder."""

import sys
from pathlib import Path

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from toon import DecodeOptions, decode


class TestPrimitives:
    """Test decoding of primitive values."""

    def test_null(self):
        assert decode("null") is None

    def test_true(self):
        assert decode("true") is True

    def test_false(self):
        assert decode("false") is False

    def test_integer(self):
        assert decode("42") == 42
        assert decode("-17") == -17
        assert decode("0") == 0

    def test_float(self):
        assert decode("3.14") == 3.14
        assert decode("-2.5") == -2.5

    def test_simple_string(self):
        assert decode("hello") == "hello"

    def test_quoted_string(self):
        assert decode('"hello world"') == "hello world"

    def test_empty_quoted_string(self):
        assert decode('""') == ""


class TestObjects:
    """Test decoding of objects."""

    def test_simple_object(self):
        result = decode("name: Alice\nage: 30")
        assert result == {"name": "Alice", "age": 30}

    def test_nested_object(self):
        result = decode("user:\n  name: Bob\n  role: admin")
        assert result == {"user": {"name": "Bob", "role": "admin"}}

    def test_empty_nested_object(self):
        result = decode("data:")
        assert result == {"data": {}}

    def test_deeply_nested(self):
        result = decode("a:\n  b:\n    c: 1")
        assert result == {"a": {"b": {"c": 1}}}

    def test_quoted_key(self):
        result = decode('"key with spaces": value')
        assert result == {"key with spaces": "value"}


class TestArraysInline:
    """Test decoding of inline primitive arrays."""

    def test_string_array(self):
        result = decode("tags[3]: a,b,c")
        assert result == {"tags": ["a", "b", "c"]}

    def test_number_array(self):
        result = decode("nums[3]: 1,2,3")
        assert result == {"nums": [1, 2, 3]}

    def test_mixed_primitives(self):
        result = decode("mix[4]: 1,two,true,null")
        assert result == {"mix": [1, "two", True, None]}

    def test_empty_array(self):
        result = decode("items[0]:")
        assert result == {"items": []}

    def test_single_element(self):
        result = decode("items[1]: x")
        assert result == {"items": ["x"]}


class TestArraysTabular:
    """Test decoding of tabular arrays."""

    def test_simple_tabular(self):
        result = decode("users[2]{id,name}:\n  1,Alice\n  2,Bob")
        assert result == {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}

    def test_tabular_with_quoted_values(self):
        result = decode('data[2]{key}:\n  "a,b"\n  "c,d"')
        assert result == {"data": [{"key": "a,b"}, {"key": "c,d"}]}

    def test_tabular_single_field(self):
        result = decode("items[2]{value}:\n  10\n  20")
        assert result == {"items": [{"value": 10}, {"value": 20}]}


class TestArraysList:
    """Test decoding of list format arrays."""

    def test_primitive_list(self):
        result = decode("items[3]:\n  - 1\n  - 2\n  - 3")
        assert result == {"items": [1, 2, 3]}

    def test_object_list(self):
        result = decode("items[2]:\n  - a: 1\n  - a: 2")
        assert result == {"items": [{"a": 1}, {"a": 2}]}

    def test_nested_object_list(self):
        result = decode("items[2]:\n  - a:\n      b: 1\n  - a:\n      b: 2")
        assert result == {"items": [{"a": {"b": 1}}, {"a": {"b": 2}}]}

    def test_mixed_list(self):
        result = decode("items[3]:\n  - 1\n  - x: 2\n  - three")
        assert result == {"items": [1, {"x": 2}, "three"]}

    def test_empty_object_in_list(self):
        result = decode("items[1]:\n  -")
        assert result == {"items": [{}]}


class TestRootArray:
    """Test decoding of root-level arrays."""

    def test_root_inline(self):
        result = decode("[3]: 1,2,3")
        assert result == [1, 2, 3]

    def test_root_tabular(self):
        result = decode("[2]{a}:\n  1\n  2")
        assert result == [{"a": 1}, {"a": 2}]

    def test_root_list(self):
        result = decode("[2]:\n  - a: 1\n  - a: 2")
        assert result == [{"a": 1}, {"a": 2}]


class TestEscapeSequences:
    """Test string escape sequence decoding (critical for multiline!)."""

    def test_newline_escape(self):
        result = decode('content: "line1\\nline2"')
        assert result == {"content": "line1\nline2"}

    def test_tab_escape(self):
        result = decode('content: "col1\\tcol2"')
        assert result == {"content": "col1\tcol2"}

    def test_carriage_return_escape(self):
        result = decode('content: "line1\\rline2"')
        assert result == {"content": "line1\rline2"}

    def test_backslash_escape(self):
        result = decode('path: "C:\\\\Users\\\\name"')
        assert result == {"path": "C:\\Users\\name"}

    def test_quote_escape(self):
        result = decode('msg: "He said \\"hello\\""')
        assert result == {"msg": 'He said "hello"'}

    def test_multiple_escapes(self):
        result = decode('text: "Line 1\\nLine 2\\twith \\"quotes\\""')
        assert result == {"text": 'Line 1\nLine 2\twith "quotes"'}

    def test_multiline_code(self):
        """The critical test - multiline content must be properly decoded."""
        toon = 'code: "def hello():\\n    print(\\"Hello, World!\\")\\n    return True"'
        result = decode(toon)
        expected = """def hello():
    print("Hello, World!")
    return True"""
        assert result == {"code": expected}


class TestPathExpansion:
    """Test dotted path expansion."""

    def test_simple_expansion(self):
        result = decode("a.b.c: 1", DecodeOptions(expand_paths=True))
        assert result == {"a": {"b": {"c": 1}}}

    def test_multiple_paths(self):
        result = decode("a.b: 1\na.c: 2", DecodeOptions(expand_paths=True))
        assert result == {"a": {"b": 1, "c": 2}}

    def test_mixed_paths(self):
        result = decode("a.b: 1\nc: 2", DecodeOptions(expand_paths=True))
        assert result == {"a": {"b": 1}, "c": 2}

    def test_no_expansion_by_default(self):
        result = decode("a.b.c: 1")
        assert result == {"a.b.c": 1}

    def test_quoted_path_not_expanded(self):
        result = decode('"a.b.c": 1', DecodeOptions(expand_paths=True))
        assert result == {"a.b.c": 1}


class TestDelimiters:
    """Test delimiter handling."""

    def test_tab_delimiter(self):
        result = decode("items[3\t]: 1\t2\t3")
        assert result == {"items": [1, 2, 3]}

    def test_pipe_delimiter(self):
        result = decode("items[3|]: 1|2|3")
        assert result == {"items": [1, 2, 3]}

    def test_tabular_tab_delimiter(self):
        result = decode("users[2\t]{id\tname}:\n  1\tAlice\n  2\tBob")
        assert result == {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}


class TestStrictMode:
    """Test strict mode validation."""

    def test_array_length_mismatch(self):
        with pytest.raises(ValueError, match="length mismatch"):
            decode("items[5]: 1,2,3", DecodeOptions(strict=True))

    def test_tabular_field_count_mismatch(self):
        with pytest.raises(ValueError, match="Expected"):
            decode("items[2]{a,b}:\n  1\n  2", DecodeOptions(strict=True))

    def test_list_count_mismatch(self):
        with pytest.raises(ValueError, match="length mismatch"):
            decode("items[5]:\n  - 1\n  - 2", DecodeOptions(strict=True))


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_input(self):
        assert decode("") is None
        assert decode("   ") is None

    def test_only_whitespace_lines(self):
        assert decode("\n\n") is None

    def test_unterminated_string(self):
        with pytest.raises(SyntaxError, match="Unterminated"):
            decode('key: "unterminated')

    def test_invalid_escape_sequence(self):
        with pytest.raises(SyntaxError, match="Invalid escape"):
            decode('key: "bad\\x"')

    def test_backslash_at_end(self):
        # A backslash followed by quote is an escaped quote, making string unterminated
        with pytest.raises(SyntaxError, match="Unterminated string"):
            decode('key: "trailing\\"')

    def test_numeric_string_preserved(self):
        result = decode('id: "007"')
        assert result == {"id": "007"}

    def test_leading_zeros_string(self):
        # "007" looks like a number but isn't
        result = decode("id: 007")
        assert result == {"id": "007"}

    def test_negative_zero(self):
        result = decode("value: -0")
        assert result == {"value": 0}


class TestComplexStructures:
    """Test complex nested structures."""

    def test_object_with_multiple_arrays(self):
        result = decode("tags[2]: a,b\nnums[3]: 1,2,3")
        assert result == {"tags": ["a", "b"], "nums": [1, 2, 3]}

    def test_array_of_arrays(self):
        result = decode("matrix[2]:\n  - [2]: 1,2\n  - [2]: 3,4")
        assert result == {"matrix": [[1, 2], [3, 4]]}

    def test_deeply_nested_structure(self):
        toon = """root:
  level1:
    level2:
      level3: value
      items[2]: a,b"""
        result = decode(toon)
        assert result == {
            "root": {"level1": {"level2": {"level3": "value", "items": ["a", "b"]}}}
        }
