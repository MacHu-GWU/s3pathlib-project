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

## Code Style

Write plain branches: explicit `if` / `else` and named temporaries. No star-unpacking to build tuples, no truthiness tricks such as `x or ""`. Re-raise with a bare `raise`, not `raise e`.

Format with `uvx ruff format` (library and tests) before committing; check unused names with `uvx ruff check --select F401,F821,F841 s3pathlib tests`.

Modules whose name starts with `_` (`_arg.py`, `better_client/_paginate.py`) are private to the package: other subpackages may import them, `s3pathlib.api` never exports them.

A public method that passes its arguments on to another method or to boto3 does it explicitly (`x=x`), with the same public signature. Every such forwarding has a test that sends a distinct value for every argument and checks that it arrives (e.g. `test_touch_arguments_passed_to_boto3`), so a forgotten line cannot silently drop an argument.

## Type Hints

Python 3.11+ syntax: `X | None`, `A | B`, `list[str]`, `dict[str, int]`, `type[X]`; never `T.Optional` / `T.Union` / `T.List` / `T.Dict` / `T.Tuple` / `T.Type`. Every module with type annotations starts with `from __future__ import annotations`, so forward references need no quotes (`-> S3Path | None`). Pure re-export modules (`__init__.py`, `api.py`) don't need it.

## Docstrings

3.0.0 is the baseline; its public API is listed in `release-history.rst`. Only use `.. versionadded::` / `.. versionchanged::` for changes after 3.0.0.

Keep docstrings thin: say what the code cannot say, not what it already says.

- A public method says three things: what it does; the behavior boto3's own docs do not describe (metadata snapshot, conditional write, side effects, not atomic); the errors it raises (`:raises`).
- Arguments passed on to boto3 are not documented one by one. Name the boto3 method in the text ("a wrapper of `get_object`") and link it once. Only document the arguments that s3pathlib adds or whose meaning differs from boto3.
- boto3 links use `https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/<method>.html`, built from the method name, which must also appear in the text so the reader can still find the API when a URL moves.
- Keep at most one `>>>` example per method, and only when it shows something that is not obvious (a return type, a snapshot, a conditional write, an error). Every `>>>` example must pass `doctest`; an example that needs data in AWS that it does not create itself is a code block without `>>>`.
- Module-level reasons (why it works this way, what was rejected) go in a `**Design notes**` section of the module docstring: one short heading per decision, then one or two sentences. A reason that holds for one line only is a comment next to that line. Rules that span modules belong here in `CLAUDE.md`.
- Comments and docstrings explain why, never how; do not restate the code.
- Never write "2.x did X" in code or tests. State the reason on its own terms; version history belongs in `release-history.rst`.

## Argument Defaults

- An argument passed on to boto3 (`version_id`, `if_match`, `metadata`, ...) defaults to `OPT` from `s3pathlib/_arg.py` ("do not send it"); build the call with `remove_optional(...)`. `None` is not "not given": it is kept, and botocore rejects it (`ParamValidationError`).
- An argument of s3pathlib itself (`s3_client`, `limit`, `region`, `encoding`, ...) defaults to `None` or a plain value, never `OPT`.
- `_arg` is private: never export `OPT` from `s3pathlib.api`.

## Errors

Raise AWS errors as is when they are usable; convert them only when they are not.

- Raise as is: errors of AWS calls with a response body (get, list, tagging, copy, delete, ...). boto3 gives named, documented errors (`NoSuchKey`, `NoSuchBucket`, `AccessDenied`) that users and AI already know how to catch.
- Use `s3pathlib.exc`: for s3pathlib's own rules and features (wrong path type, `overwrite=False`, `ignore_not_found`), and for HEAD calls (`head_bucket`, `head_object`), whose errors are a bare `"404"` / `"403"` that `s3_client.exceptions.*` cannot catch. Always `raise ... from e`.
- Recognize an AWS error by `e.response["Error"]["Code"]` or a modeled exception, never by the message text.

Which exception for which mistake of the caller (all `s3pathlib.exc` classes inherit `S3PathlibError` and the matching builtin, so a generic `except` still works):

| Situation | Exception | Example |
|---|---|---|
| An argument of the wrong Python type | builtin `TypeError`, with a message (like `pathlib.Path(1)`) | `S3Path(1)`, `joinpath(1)` |
| Arguments that conflict, or an invalid value | builtin `ValueError`, with a message | `change(new_dirpath=..., new_dirname=...)`, `limit=-1` |
| The wrong kind of path (a dir where a file is needed, ...) | `exc.S3PathTypeError` or a subclass (`S3PathIsNotFileError`, `S3PathIsNotFolderError`, `S3PathIsNotBucketError`, `S3PathIsNotRelpathError`) | `fname` of a dir, `read_bytes` of a bucket |
| Invalid data or format (URI, ARN, partition, state) | `exc.S3ValidationError` | `S3Path("https://...")`, `from_dict({...})` |

Show a path in an error message with `p._error_label()`: the URI when it has a bucket, otherwise the repr; never `None`.

## Deprecation

- A whole function, method or class: put `s3pathlib.marker.deprecated` (PEP 702) directly on it, with the message `Deprecated since X, will be removed in Y. Use Z instead.`.
- One way of calling it (e.g. an argument): `warnings.warn(..., DeprecationWarning, stacklevel=n)`, where `stacklevel` points at the user's line. When several public entry points share one private implementation, make all of them call it directly so the depth is the same (`joinpath` and `/` call `_joinpath`), and write the call path in a comment next to the `stacklevel`. A test asserts `record[0].filename == __file__`; a test module about deprecations starts with `pytestmark = pytest.mark.filterwarnings("error::DeprecationWarning")`.
- A warning that is not a deprecation but should point at the user's line from several entry points computes its `stacklevel` by walking out of the package (see `s3pathlib/metadata.py`).

## Tests

- Tests live in `tests/`, mirroring the source tree. Directories stay the same; file names get the full path as a prefix, e.g. `s3pathlib/core/copy.py` is tested by `tests/core/test_core_copy.py`.
- Each test file can also run on its own (`.venv/bin/python tests/core/test_core_copy.py`) to get coverage for just that module.
- Tests that call AWS use `BaseTest` from `s3pathlib/tests/mock_aws.py` (its module docstring has the full rules). Test logic goes in a mixin; each mode is a one-line subclass: `class TestMock(Mixin): use_mock = True` and `class TestRealAws(Mixin): use_mock = False`. Helpers for recording API calls and building clients are in `s3pathlib/tests/aws_helpers.py`.
- Every test module that uses `BaseTest` has both classes, and both are committed. Mark a test that cannot run in one mode with `@mock_only("reason")` or `@real_aws_only("reason")`; leave out `TestRealAws` only if the whole module cannot run on AWS, with a comment saying why.
- When tests run:
  - `TestMock` always runs, against moto.
  - `TestRealAws` runs only when BOTH (1) the test can run on AWS: the class exists and the test is not `@mock_only`; and (2) the run allows AWS: `S3PATHLIB_TEST_REAL_AWS=true`. Neither overrides the other. Otherwise the class is skipped with the reason.
  - `S3PATHLIB_TEST_REAL_AWS` must be unset, `true` or `false`; any other value is an error. With `true`, missing credentials are an error, not a skip.
  - `mise run cov` runs moto only; `mise run cov-aws` also runs real AWS (profile `S3PATHLIB_TEST_AWS_PROFILE` from `mise.toml`, created by `mise run setup-aws-ci`).
- `tests/test_boto3_links.py` checks the boto3 links offline. Run `sphinx-build -b linkcheck` before a release to check that the pages exist.
- Keep tests thin: a test docstring is one or two lines saying what is verified and why it matters; tests that fail together for the same bug are merged or parametrized; each test module keeps a module docstring with its test order. Differences between moto and real AWS that were measured go in a comment next to the test that depends on them, not in version history.
- Each test writes under its own folder `self.s3dir_test` (or `self.s3dir_test_with_versioning`); never depend on test order. On real AWS, the class folder is emptied when the class starts. Verify S3 state with native `self.s3_client` calls, not with s3pathlib itself.
