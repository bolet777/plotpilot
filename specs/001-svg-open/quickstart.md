# Quickstart: 001-svg-open

## Run the app

```bash
cd plotpilot
uv run plotpilot
```

Use **File → Open SVG…** or **Cmd+O**, choose `tests/fixtures/valid_basic.svg`.

The main window should show the loaded file name.

## Run tests

```bash
uv run pytest tests/test_svg_parse.py tests/test_svg_loader.py
uv run ruff check src tests
uv run ruff format --check src tests
```
