# TOON Python

A production-ready Python implementation of TOON (Token-Oriented Object Notation) - a token-efficient JSON alternative optimized for LLM tool calls.

## Features

- **~40% Token Savings**: Compact indentation-based format reduces token usage
- **Full JSON Data Model**: Complete compatibility with JSON types
- **Proper Escape Sequences**: Correct handling of multiline strings via `\n`, `\t`, `\r`, `\\`, `\"`
- **Multiple Array Formats**: Inline, tabular (CSV-like), and list formats
- **Key Folding**: Optional dotted path compression (`a.b.c: value`)
- **Path Expansion**: Optional nested object reconstruction from dotted keys
- **Streaming Support**: Memory-efficient `encode_lines()` generator
- **Async Support**: `decode_stream_async()` for async iterables
- **Strict Mode**: Comprehensive validation for production use

## Installation

```bash
pip install toon-format
```

## Quick Start

```python
import toon

# Encode Python data to TOON
data = {"name": "Alice", "tags": ["admin", "user"]}
encoded = toon.encode(data)
# Output:
# name: Alice
# tags[2]: admin,user

# Decode TOON to Python data
decoded = toon.decode(encoded)
assert decoded == data
```

## Multiline Strings

TOON properly handles multiline content using escape sequences:

```python
import toon

code = """def hello():
    print("Hello, World!")
    return True"""

data = {"code": code}
encoded = toon.encode(data)
# Output: code: "def hello():\n    print(\"Hello, World!\")\n    return True"

decoded = toon.decode(encoded)
assert decoded["code"] == code  # Multiline preserved!
```

## Array Formats

TOON automatically selects the most compact array representation:

### Inline Primitive Arrays
```python
# {"tags": ["a", "b", "c"]} encodes to:
# tags[3]: a,b,c
```

### Tabular Arrays (CSV-like)
```python
# {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]} encodes to:
# users[2]{id,name}:
#   1,Alice
#   2,Bob
```

### List Arrays
```python
# {"items": [{"nested": {"deep": 1}}, {"nested": {"deep": 2}}]} encodes to:
# items[2]:
#   - nested:
#       deep: 1
#   - nested:
#       deep: 2
```

## Options

### Encoding Options

```python
from toon import encode, EncodeOptions

# Custom indentation
encoded = encode(data, EncodeOptions(indent=4))

# Key folding (dotted paths)
encoded = encode(
    {"a": {"b": {"c": 1}}},
    EncodeOptions(key_folding="safe")
)
# Output: a.b.c: 1

# Alternative delimiters
encoded = encode(data, EncodeOptions(delimiter="\t"))  # Tab delimiter
encoded = encode(data, EncodeOptions(delimiter="|"))   # Pipe delimiter
```

### Decoding Options

```python
from toon import decode, DecodeOptions

# Strict mode (validates counts, structure)
decoded = decode(text, DecodeOptions(strict=True))

# Path expansion (expand dotted keys to nested objects)
decoded = decode("a.b.c: 1", DecodeOptions(expand_paths=True))
# Result: {"a": {"b": {"c": 1}}}
```

## Streaming API

### Memory-efficient encoding

```python
from toon import encode_lines

for line in encode_lines(large_data):
    print(line)
```

### Async decoding

```python
from toon import decode_stream_async

async def process_lines():
    async for line in some_async_source():
        yield line

result = await decode_stream_async(process_lines())
```

## API Reference

### Main Functions

| Function | Description |
|----------|-------------|
| `encode(value, options=None)` | Encode Python value to TOON string |
| `encode_lines(value, options=None)` | Generator yielding TOON lines |
| `decode(text, options=None)` | Decode TOON string to Python value |
| `decode_lines(lines, options=None)` | Decode from pre-split lines |
| `decode_stream_async(lines, options=None)` | Decode from async iterable |

### EncodeOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `indent` | `int` | `2` | Spaces per indentation level |
| `delimiter` | `str` | `","` | Delimiter for arrays (`","`, `"\t"`, `"\|"`) |
| `key_folding` | `str` | `"none"` | Key folding mode (`"none"`, `"safe"`) |
| `flatten_depth` | `int\|None` | `None` | Max folding depth |

### DecodeOptions

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `strict` | `bool` | `False` | Enable strict validation |
| `expand_paths` | `bool` | `False` | Expand dotted keys |
| `indent` | `int` | `2` | Expected indent size (strict mode) |

## Comparison with python-toon

| Feature | python-toon | toon-format |
|---------|-------------|-------------|
| Multiline strings | Broken (`\|` literal) | Proper escape sequences |
| Array formats | Limited | All 3 (inline, tabular, list) |
| Key folding | No | Yes (encode) |
| Path expansion | No | Yes (decode) |
| Streaming | No | Yes (`encode_lines`) |
| Async support | No | Yes (`decode_stream_async`) |
| Spec compliance | Partial | Full TOON v3.0 |

## License

MIT
