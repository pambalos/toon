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


class TestBlockScalars:
    """Test YAML-style block scalar support (|, >, etc.)."""

    def test_literal_block_scalar_basic(self):
        """Test basic literal block scalar with |."""
        toon = """content: |
  Line 1
  Line 2
  Line 3"""
        result = decode(toon)
        assert result == {"content": "Line 1\nLine 2\nLine 3\n"}

    def test_literal_block_scalar_preserves_blank_lines(self):
        """Test that literal block scalar preserves blank lines."""
        toon = """content: |
  Line 1

  Line 2 after blank

  Line 3"""
        result = decode(toon)
        assert result == {"content": "Line 1\n\nLine 2 after blank\n\nLine 3\n"}

    def test_literal_strip_chomping(self):
        """Test |- removes trailing newline."""
        toon = """content: |-
  Line 1
  Line 2"""
        result = decode(toon)
        assert result == {"content": "Line 1\nLine 2"}

    def test_literal_keep_chomping(self):
        """Test |+ preserves all trailing newlines."""
        toon = """content: |+
  Line 1
  Line 2

"""
        result = decode(toon)
        # |+ preserves trailing blank lines as newlines
        assert result == {"content": "Line 1\nLine 2\n\n\n"}

    def test_folded_block_scalar_basic(self):
        """Test folded block scalar with >."""
        toon = """content: >
  This is a long
  paragraph that
  should be folded"""
        result = decode(toon)
        assert result == {"content": "This is a long paragraph that should be folded\n"}

    def test_folded_block_scalar_preserves_paragraph_breaks(self):
        """Test that folded block scalar preserves blank line paragraph breaks."""
        toon = """content: >
  Paragraph one
  continues here.

  Paragraph two
  continues here."""
        result = decode(toon)
        assert result == {"content": "Paragraph one continues here.\n\nParagraph two continues here.\n"}

    def test_folded_strip_chomping(self):
        """Test >- removes trailing newline."""
        toon = """content: >-
  This is folded
  content"""
        result = decode(toon)
        assert result == {"content": "This is folded content"}

    def test_block_scalar_nested_in_object(self):
        """Test block scalar in nested object structure."""
        toon = """tool: write_file
input:
  path: /test/file.md
  content: |
    # Heading

    Paragraph text

    ## Subheading"""
        result = decode(toon)
        assert result == {
            "tool": "write_file",
            "input": {
                "path": "/test/file.md",
                "content": "# Heading\n\nParagraph text\n\n## Subheading\n"
            }
        }

    def test_block_scalar_with_indented_content(self):
        """Test block scalar preserves internal indentation."""
        toon = """code: |
  def hello():
      print("Hello")
      return True"""
        result = decode(toon)
        assert result == {"code": "def hello():\n    print(\"Hello\")\n    return True\n"}

    def test_block_scalar_with_markdown_list(self):
        """Test block scalar with markdown list content."""
        toon = """readme: |
  # Title

  Features:
  - Item 1
  - Item 2
  - Item 3"""
        result = decode(toon)
        assert result == {"readme": "# Title\n\nFeatures:\n- Item 1\n- Item 2\n- Item 3\n"}

    def test_multiple_block_scalars(self):
        """Test multiple block scalars in same object."""
        toon = """files:
  readme: |
    # README
    Content here
  license: |
    MIT License
    Copyright"""
        result = decode(toon)
        assert result == {
            "files": {
                "readme": "# README\nContent here\n",
                "license": "MIT License\nCopyright\n"
            }
        }

    def test_block_scalar_followed_by_sibling_key(self):
        """Test block scalar properly terminates when sibling key encountered."""
        toon = """config:
  script: |
    echo "hello"
    echo "world"
  timeout: 30"""
        result = decode(toon)
        assert result == {
            "config": {
                "script": "echo \"hello\"\necho \"world\"\n",
                "timeout": 30
            }
        }

    def test_empty_block_scalar(self):
        """Test block scalar with no content lines."""
        toon = """content: |
next_key: value"""
        result = decode(toon)
        assert result == {"content": "", "next_key": "value"}


class TestImplicitMultiline:
    """Test implicit multi-line content detection (LLM-friendly mode)."""

    def test_implicit_multiline_markdown(self):
        """Test that markdown content after inline value is captured."""
        toon = """content: # Heading

## Overview
Some paragraph text.

- List item 1
- List item 2"""
        result = decode(toon)
        expected = "# Heading\n\n## Overview\nSome paragraph text.\n\n- List item 1\n- List item 2"
        assert result["content"] == expected

    def test_implicit_multiline_stops_at_sibling_key(self):
        """Test that implicit multiline stops at sibling TOON key."""
        toon = """input:
  content: # Heading

## Section
Paragraph here.
  mode: overwrite"""
        result = decode(toon)
        assert result["input"]["content"] == "# Heading\n\n## Section\nParagraph here."
        assert result["input"]["mode"] == "overwrite"

    def test_implicit_multiline_full_tool_call(self):
        """Test realistic LLM tool call with implicit multiline."""
        toon = """tool: write_file
input:
  path: /test/file.md
  content: # Product Roadmap

## Overview
Dashboard for agent management.

## Features
- Feature 1
- Feature 2"""
        result = decode(toon)
        assert result["tool"] == "write_file"
        assert result["input"]["path"] == "/test/file.md"
        assert "# Product Roadmap" in result["input"]["content"]
        assert "## Overview" in result["input"]["content"]
        assert "- Feature 1" in result["input"]["content"]

    def test_toon_list_not_affected(self):
        """Test that proper TOON lists are NOT affected by implicit multiline."""
        toon = """items[2]:
  - a:
      b: 1
  - a:
      b: 2"""
        result = decode(toon)
        assert result == {"items": [{"a": {"b": 1}}, {"a": {"b": 2}}]}

    def test_simple_inline_not_affected(self):
        """Test that simple inline values don't trigger implicit multiline."""
        toon = """name: Alice
age: 30
active: true"""
        result = decode(toon)
        assert result == {"name": "Alice", "age": 30, "active": True}

    def test_implicit_multiline_with_colons_in_content(self):
        """Test content with colons (like URLs) doesn't break parsing."""
        toon = """content: # Links

Check out https://example.com for more info.

See also: related docs
next: value"""
        result = decode(toon)
        assert "https://example.com" in result["content"]
        assert result["next"] == "value"


class TestSingleQuotedStrings:
    """Test single-quoted string support."""

    def test_single_quoted_string(self):
        """Basic single-quoted string."""
        assert decode("value: 'hello'") == {"value": "hello"}

    def test_single_quoted_empty(self):
        """Empty single-quoted string."""
        assert decode("value: ''") == {"value": ""}

    def test_single_quoted_with_spaces(self):
        """Single-quoted string with spaces."""
        assert decode("value: 'hello world'") == {"value": "hello world"}

    def test_single_quoted_json(self):
        """Single-quoted JSON string (the problem case)."""
        result = decode('value: \'{"key": "val"}\'')
        assert result == {"value": '{"key": "val"}'}

    def test_single_quoted_with_double_quotes(self):
        """Single-quoted string containing double quotes."""
        assert decode('value: \'he said "hi"\'') == {"value": 'he said "hi"'}

    def test_single_quoted_escaped_single(self):
        """Escaped single quote inside single-quoted string."""
        assert decode("value: 'it\\'s fine'") == {"value": "it's fine"}

    def test_nested_input_single_quoted(self):
        """Nested object with single-quoted value."""
        result = decode("""tool: test
input:
  data: '{"nested": true}'""")
        assert result == {
            "tool": "test",
            "input": {"data": '{"nested": true}'}
        }


class TestHeredoc:
    """Test heredoc syntax support (<<TAG ... TAG)."""

    def test_basic_heredoc(self):
        """Test basic heredoc syntax."""
        toon = """content: <<END
line 1
line 2
line 3
END"""
        result = decode(toon)
        assert result == {"content": "line 1\nline 2\nline 3"}

    def test_heredoc_with_content_tag(self):
        """Test heredoc with CONTENT tag."""
        toon = """data: <<CONTENT
hello world
CONTENT"""
        result = decode(toon)
        assert result == {"data": "hello world"}

    def test_heredoc_with_eof_tag(self):
        """Test heredoc with EOF tag."""
        toon = """text: <<EOF
some text
EOF"""
        result = decode(toon)
        assert result == {"text": "some text"}

    def test_heredoc_typescript_interface(self):
        """Test heredoc with TypeScript interface - the main use case."""
        toon = """tool: write_file
input:
  path: /path/to/file.tsx
  content: <<CONTENT
interface FileNode {
  name: string
  path: string
  type: "file"
}
CONTENT"""
        result = decode(toon)
        assert result == {
            "tool": "write_file",
            "input": {
                "path": "/path/to/file.tsx",
                "content": 'interface FileNode {\n  name: string\n  path: string\n  type: "file"\n}'
            }
        }

    def test_heredoc_with_colons(self):
        """Test heredoc preserves lines that look like key:value."""
        toon = """content: <<END
name: string
path: string
type: "file"
END"""
        result = decode(toon)
        assert result == {"content": 'name: string\npath: string\ntype: "file"'}

    def test_heredoc_preserves_indentation(self):
        """Test heredoc preserves internal indentation."""
        toon = """code: <<CODE
def hello():
    print("Hello")
    if True:
        return 1
CODE"""
        result = decode(toon)
        assert result == {"code": 'def hello():\n    print("Hello")\n    if True:\n        return 1'}

    def test_heredoc_with_blank_lines(self):
        """Test heredoc preserves blank lines."""
        toon = """content: <<END
line 1

line 3
END"""
        result = decode(toon)
        assert result == {"content": "line 1\n\nline 3"}

    def test_heredoc_followed_by_sibling_key(self):
        """Test heredoc properly terminates and sibling key is parsed."""
        toon = """input:
  content: <<CONTENT
interface Props {
  name: string
}
CONTENT
  mode: overwrite"""
        result = decode(toon)
        assert result == {
            "input": {
                "content": "interface Props {\n  name: string\n}",
                "mode": "overwrite"
            }
        }

    def test_heredoc_empty_content(self):
        """Test heredoc with no content between tags."""
        toon = """content: <<END
END"""
        result = decode(toon)
        assert result == {"content": ""}

    def test_heredoc_with_tag_in_content(self):
        """Test that tag inside content doesn't close heredoc (only stripped line match)."""
        toon = """content: <<END
The END is near
But not END yet
END"""
        result = decode(toon)
        assert result == {"content": "The END is near\nBut not END yet"}

    def test_heredoc_nested_code_blocks(self):
        """Test heredoc with markdown code blocks inside."""
        toon = """readme: <<CONTENT
# README

```typescript
interface Config {
  port: number
}
```

## Usage
CONTENT"""
        result = decode(toon)
        expected = """# README

```typescript
interface Config {
  port: number
}
```

## Usage"""
        assert result == {"readme": expected}

    def test_heredoc_missing_tag_raises_error(self):
        """Test that heredoc without tag raises SyntaxError."""
        with pytest.raises(SyntaxError, match="Heredoc requires a tag"):
            decode("content: <<")

    def test_heredoc_realistic_write_file(self):
        """Test realistic write_file tool call with TypeScript."""
        toon = """tool: write_file
input:
  path: src/types/user.ts
  content: <<CONTENT
export interface User {
  id: string
  name: string
  email: string
  role: "admin" | "user"
  createdAt: Date
}

export interface UserProfile extends User {
  avatar: string
  bio: string
}
CONTENT"""
        result = decode(toon)
        assert result["tool"] == "write_file"
        assert result["input"]["path"] == "src/types/user.ts"
        assert "export interface User {" in result["input"]["content"]
        assert "id: string" in result["input"]["content"]
        assert "export interface UserProfile extends User {" in result["input"]["content"]

    def test_heredoc_with_yaml_like_content(self):
        """Test heredoc with YAML-like content."""
        toon = """config: <<YAML
server:
  host: localhost
  port: 8080
database:
  name: mydb
  user: admin
YAML"""
        result = decode(toon)
        assert "server:" in result["config"]
        assert "host: localhost" in result["config"]
        assert "database:" in result["config"]
