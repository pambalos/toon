"""Round-trip tests for TOON encode/decode."""

import sys
from pathlib import Path

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from toon import decode, encode


def roundtrip(data):
    """Encode then decode, returning the result."""
    encoded = encode(data)
    return decode(encoded)


class TestRoundtripPrimitives:
    """Test round-trip for primitive values."""

    def test_null(self):
        assert roundtrip(None) is None

    def test_booleans(self):
        assert roundtrip(True) is True
        assert roundtrip(False) is False

    def test_integers(self):
        assert roundtrip(42) == 42
        assert roundtrip(-17) == -17
        assert roundtrip(0) == 0

    def test_floats(self):
        assert roundtrip(3.14) == 3.14
        assert roundtrip(-2.5) == -2.5

    def test_strings(self):
        assert roundtrip("hello") == "hello"
        assert roundtrip("hello world") == "hello world"
        assert roundtrip("") == ""


class TestRoundtripObjects:
    """Test round-trip for objects."""

    def test_simple_object(self):
        data = {"name": "Alice", "age": 30}
        assert roundtrip(data) == data

    def test_nested_object(self):
        data = {"user": {"name": "Bob", "role": "admin"}}
        assert roundtrip(data) == data

    def test_empty_object(self):
        data = {"data": {}}
        assert roundtrip(data) == data

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": {"e": 1}}}}}
        assert roundtrip(data) == data


class TestRoundtripArrays:
    """Test round-trip for arrays."""

    def test_primitive_array(self):
        data = {"items": [1, 2, 3]}
        assert roundtrip(data) == data

    def test_string_array(self):
        data = {"tags": ["alpha", "beta", "gamma"]}
        assert roundtrip(data) == data

    def test_empty_array(self):
        data = {"items": []}
        assert roundtrip(data) == data

    def test_tabular_array(self):
        data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
        assert roundtrip(data) == data

    def test_list_array(self):
        data = {"items": [{"a": {"b": 1}}, {"a": {"b": 2}}]}
        assert roundtrip(data) == data

    def test_mixed_array(self):
        data = {"items": [1, "two", True, None]}
        assert roundtrip(data) == data

    def test_nested_arrays(self):
        data = {"matrix": [[1, 2], [3, 4]]}
        assert roundtrip(data) == data


class TestRoundtripEscapeSequences:
    """Test round-trip for escaped strings (CRITICAL for multiline!)."""

    def test_newline(self):
        data = {"content": "line1\nline2"}
        assert roundtrip(data) == data

    def test_tab(self):
        data = {"content": "col1\tcol2"}
        assert roundtrip(data) == data

    def test_carriage_return(self):
        data = {"content": "line1\rline2"}
        assert roundtrip(data) == data

    def test_backslash(self):
        data = {"path": "C:\\Users\\name"}
        assert roundtrip(data) == data

    def test_quotes(self):
        data = {"msg": 'He said "hello"'}
        assert roundtrip(data) == data

    def test_mixed_escapes(self):
        data = {"text": 'Line 1\nLine 2\twith "quotes" and \\backslash'}
        assert roundtrip(data) == data

    def test_multiline_code(self):
        """The critical test - multiline content must round-trip correctly."""
        data = {
            "code": """def hello():
    print("Hello, World!")
    return True"""
        }
        result = roundtrip(data)
        assert result == data
        assert result["code"] == data["code"]

    def test_multiline_json(self):
        """Test multiline JSON-like content."""
        data = {
            "json": """{
    "name": "test",
    "values": [1, 2, 3]
}"""
        }
        assert roundtrip(data) == data

    def test_multiline_markdown(self):
        """Test multiline markdown content."""
        data = {
            "readme": """# Title

## Section 1

Some text here.

## Section 2

More text."""
        }
        assert roundtrip(data) == data

    def test_file_content_simulation(self):
        """Simulate writing file content through TOON (the bug scenario)."""
        file_content = """import os

def main():
    path = os.getcwd()
    print(f"Current directory: {path}")

if __name__ == "__main__":
    main()
"""
        data = {"file_path": "/tmp/test.py", "content": file_content}
        result = roundtrip(data)
        assert result == data
        assert result["content"] == file_content


class TestRoundtripComplexStructures:
    """Test round-trip for complex real-world structures."""

    def test_tool_call_with_file_content(self):
        """Simulate LLM tool call for file writing."""
        data = {
            "tool": "write_file",
            "arguments": {
                "path": "/project/src/main.py",
                "content": """#!/usr/bin/env python3
\"\"\"Main module.\"\"\"

import sys

def main():
    print("Hello")
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
            },
        }
        result = roundtrip(data)
        assert result == data

    def test_api_response_with_nested_data(self):
        """Simulate API response."""
        data = {
            "status": "success",
            "data": {
                "users": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com"},
                    {"id": 2, "name": "Bob", "email": "bob@example.com"},
                ],
                "pagination": {"page": 1, "total": 100, "per_page": 10},
            },
            "meta": {"timestamp": "2024-01-15T10:30:00Z", "version": "1.0"},
        }
        assert roundtrip(data) == data

    def test_config_with_special_characters(self):
        """Test config containing special characters."""
        data = {
            "database": {
                "connection_string": "postgresql://user:p@ss:word@localhost/db",
                "query": 'SELECT * FROM users WHERE name = "test"',
            },
            "paths": {"home": "/Users/test", "windows": "C:\\Users\\test"},
        }
        assert roundtrip(data) == data


class TestRoundtripRootValues:
    """Test round-trip for root-level values."""

    def test_root_array(self):
        data = [1, 2, 3]
        assert roundtrip(data) == data

    def test_root_object_array(self):
        data = [{"a": 1}, {"a": 2}]
        assert roundtrip(data) == data


class TestRoundtripEdgeCases:
    """Test round-trip for edge cases."""

    def test_special_keys(self):
        """Test keys that need quoting."""
        data = {
            "normal": 1,
            "with space": 2,
            "with:colon": 3,
            "with[bracket]": 4,
        }
        assert roundtrip(data) == data

    def test_values_that_look_like_literals(self):
        """Test string values that look like literals."""
        data = {
            "str_true": "true",
            "str_false": "false",
            "str_null": "null",
            "str_num": "123",
        }
        # Note: These will be quoted in TOON
        result = roundtrip(data)
        assert result == data
        assert isinstance(result["str_true"], str)
        assert isinstance(result["str_num"], str)

    def test_empty_string_value(self):
        data = {"empty": ""}
        assert roundtrip(data) == data

    def test_string_with_only_spaces(self):
        data = {"spaces": "   "}
        assert roundtrip(data) == data

    def test_unicode_content(self):
        data = {"emoji": "Hello ", "chinese": "", "math": ""}
        assert roundtrip(data) == data
