# Contract: SVG loader

## `load_svg_from_path(path: Path) -> SvgDocument`

**Preconditions**: `path` is the user-selected filesystem path (absolute or relative).

**Success**: Returns `SvgDocument` with absolute `path`, `name == path.name`, non-empty
`raw_text` for valid fixtures, and `root` whose local tag is `svg`.

**Failure**: Raises `SvgLoadError` with `user_message` and `kind`:

| kind | When |
|------|------|
| `missing` | Path does not exist |
| `unreadable` | Exists but cannot be read (permissions, I/O) |
| `encoding` | Bytes are not valid UTF-8 |
| `xml` | Not well-formed XML |
| `not_svg` | Well-formed XML but root is not SVG |

**Idempotency**: Read-only; no global mutable state in the service.

## `parse_svg_text(text: str) -> Element`

**Success**: Returns root element for well-formed SVG text.

**Failure**: Raises `SvgParseError` (subtypes or same kinds as above for xml/not_svg).

Pure function; no filesystem access.
