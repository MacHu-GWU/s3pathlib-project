# s3pathlib

An SDK on top of AWS boto3 S3 that gives a human-friendly, `pathlib`-like API.

## Tooling

- `mise` manages Python, uv and Claude Code (`mise.toml`). Run tasks with `mise run <task>`; tests are `mise run cov`.
- `uv` manages packages (`pyproject.toml`, `uv.lock`).
- The virtualenv is `.venv`; use `.venv/bin/python`.

## Import Style

One name per import line:

```python
from .abc import efg
from .abc import xyz
```

Order: `import typing as T` first, then standard library, then third-party, then s3pathlib's own relative imports.

## Docstrings

3.0.0 is the baseline; its public API is listed in `release-history.rst`. Only use `.. versionadded::` / `.. versionchanged::` for changes after 3.0.0.

## Tests

- Tests live in `tests/`, mirroring the source tree. Directories stay the same; file names get the full path as a prefix, e.g. `s3pathlib/core/copy.py` is tested by `tests/core/test_core_copy.py`.
- Each test file can also run on its own (`.venv/bin/python tests/core/test_core_copy.py`) to get coverage for just that module.
- `s3pathlib/tests/mock.py` provides `BaseTest`. A test class sets `use_mock = True` to run against moto, or `use_mock = False` to run against real AWS. Test logic goes in a mixin, and each mode is a one-line subclass, so switching is one flag. By default only the moto classes are enabled.
