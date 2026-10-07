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

## Type Hints

Python 3.11+ syntax: `X | None`, `A | B`, `list[str]`, `dict[str, int]`, `type[X]`; never `T.Optional` / `T.Union` / `T.List` / `T.Dict` / `T.Tuple` / `T.Type`. Every module with type annotations starts with `from __future__ import annotations`, so forward references need no quotes (`-> S3Path | None`). Pure re-export modules (`__init__.py`, `api.py`) don't need it.

## Docstrings

3.0.0 is the baseline; its public API is listed in `release-history.rst`. Only use `.. versionadded::` / `.. versionchanged::` for changes after 3.0.0.

## Tests

- Tests live in `tests/`, mirroring the source tree. Directories stay the same; file names get the full path as a prefix, e.g. `s3pathlib/core/copy.py` is tested by `tests/core/test_core_copy.py`.
- Each test file can also run on its own (`.venv/bin/python tests/core/test_core_copy.py`) to get coverage for just that module.
- Tests that call AWS use `BaseTest` from `s3pathlib/tests/mock_aws.py` (its module docstring has the full rules). Test logic goes in a mixin; each mode is a one-line subclass: `class TestMock(Mixin): use_mock = True` and `class TestRealAws(Mixin): use_mock = False`. `s3pathlib/tests/mock.py` is the older version, kept only for tests not migrated yet; do not use it in new tests.
- When you change a test file, migrate it to `mock_aws.BaseTest` and add (or uncomment) its `TestRealAws` class, and commit it. Mark a test that cannot run in one mode with `@mock_only("reason")` or `@real_aws_only("reason")`; leave out `TestRealAws` only if the whole module cannot run on AWS, with a comment saying why.
- When tests run:
  - `TestMock` always runs, against moto.
  - `TestRealAws` runs only when BOTH (1) the test can run on AWS: the class exists and the test is not `@mock_only`; and (2) the run allows AWS: `S3PATHLIB_TEST_REAL_AWS=true`. Neither overrides the other. Otherwise the class is skipped with the reason.
  - `S3PATHLIB_TEST_REAL_AWS` must be unset, `true` or `false`; any other value is an error. With `true`, missing credentials are an error, not a skip.
  - `mise run cov` runs moto only; `mise run cov-aws` also runs real AWS (profile `S3PATHLIB_TEST_AWS_PROFILE` from `mise.toml`, created by `mise run setup-aws-ci`).
- Each test writes under its own folder `self.s3dir_test` (or `self.s3dir_test_with_versioning`); never depend on test order. On real AWS, the class folder is emptied when the class starts. Verify S3 state with native `self.s3_client` calls, not with s3pathlib itself.
