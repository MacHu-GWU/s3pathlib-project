---
name: aws-real-test-infra
description: Set up, or repair, the test infrastructure of a Python library whose tests must run against both moto and a real AWS account, with a one-variable switch between them. It covers the dev and test AWS profiles in mise.toml, a narrowly scoped IAM user, idempotent boto3 setup and teardown tasks that also write the GitHub Actions secrets, the BaseTest class with TestMock / TestRealAws subclasses and @mock_only / @real_aws_only, isolated S3 prefixes per run, a GitHub Actions matrix that runs real AWS on every push, and documentation notebooks executed against AWS with the account id redacted. Use it when a project needs real AWS tests, when adding a new AWS service to such a project, or when any part of this setup is missing or broken. Everything is derived from one parameter, the package name.
---

# Real AWS + moto test infrastructure

This skill brings one standard setup into any Python library that calls AWS:

- every test that calls AWS is written once and runs against **moto** (always) and against **real AWS** (when allowed), switched by one environment variable;
- the real AWS runs use a **dedicated IAM user** that can only touch the test resources;
- one **idempotent boto3 script** creates the resources, the user, its access key, the GitHub Actions secrets, and prints the local profile to paste;
- **CI** runs the whole suite against moto and real AWS on every push;
- the **documentation notebooks** run against the same resources, and the account id is redacted before saving.

Everything is in `templates/`, derived from one parameter, `<package_name>`. Read `references/design.md` for why each piece is the way it is before changing any of it.

## The parameter and what is derived from it

Ask for `<package_name>` (the import name, e.g. `aws_foo`) if it is not obvious from `pyproject.toml`. Then:

| Placeholder | Rule | Example |
|---|---|---|
| `<package_name>` | the import name | `aws_foo` |
| `<PACKAGE_NAME>` | upper case of it | `AWS_FOO` |
| `<package-name>` | `_` replaced by `-` (AWS resource names; S3 forbids `_`) | `aws-foo` |

| Thing | Value |
|---|---|
| dev profile env var / default value | `<PACKAGE_NAME>_DEV_AWS_PROFILE` = `project_<package_name>_dev` |
| test profile env var / default value | `<PACKAGE_NAME>_TEST_AWS_PROFILE` = `project_<package_name>_test` |
| real AWS switch | `<PACKAGE_NAME>_TEST_REAL_AWS` = unset, `true` or `false` |
| GitHub secrets = CI env vars | `AWS_ACCESS_KEY_ID_FOR_GITHUB_CI`, `AWS_SECRET_ACCESS_KEY_FOR_GITHUB_CI` (fixed names) |
| IAM user / inline policy | `project-<package-name>-test` / `<package-name>-unit-test` |
| shared resources | `{account_id}-{region}-<package-name>-test[-variant]` |
| temporary resources made by tests | `<package-name>-test-tmp-{uuid}` |
| test data prefix | `projects/<package_name>/unittest/{local or ci/<GITHUB_RUN_ID>}/{sys.platform}/py{XY}/<module path>/<test name>/` |
| docs data prefix | `projects/<package_name>/docs/<notebook>/<demo>/` |
| region | `us-east-1` (one constant in `aws_ci.py` and one in `mock_aws.py`) |

Other placeholders that only appear in one template: `<module>` (test example), `<account>` / `<user>` (the `GITHUB_TOKEN` line of `mise.toml`).

## File map

| Template | Destination |
|---|---|
| `templates/root/mise.toml.tmpl` | merge into `mise.toml` |
| `templates/root/pyproject.toml.tmpl` | merge into `pyproject.toml` extras |
| `templates/root/coveragerc.tmpl` | `.coveragerc` |
| `templates/root/CLAUDE.md.tmpl` | merge into `CLAUDE.md` |
| `templates/mise-tasks/aws_ci.py.tmpl` | `.mise/tasks/aws_ci.py` (names, IAM policy, shared helpers) |
| `templates/mise-tasks/setup-aws-ci.py.tmpl` | `.mise/tasks/setup-aws-ci.py` |
| `templates/mise-tasks/teardown-aws-ci.py.tmpl` | `.mise/tasks/teardown-aws-ci.py` |
| `templates/mise-tasks/utils.py.tmpl` | `.mise/tasks/utils.py` (only `get_github_repo_info` is needed; keep the project's own file if it has it) |
| `templates/mise-tasks/docs-run.py.tmpl` | `.mise/tasks/docs-run.py` |
| `templates/package-tests/mock_aws.py.tmpl` | `<package_name>/tests/mock_aws.py` (shipped in the package) |
| `templates/package-tests/aws_helpers.py.tmpl` | `<package_name>/tests/aws_helpers.py` (optional helpers) |
| `templates/tests/test_tests_mock_aws.py.tmpl` | `tests/tests/test_tests_mock_aws.py` (tests of the framework itself) |
| `templates/tests/test_example_module.py.tmpl` | the shape of every test module that calls AWS |
| `templates/github/main.yml.tmpl` | `.github/workflows/main.yml` |
| `templates/github/README.rst.tmpl` | `.github/workflows/README.rst` |
| `templates/docs/notebook-setup-cell.md.tmpl` | the first cells of every notebook |

The templates end in `.tmpl` so that pytest and linters never pick them up inside the skill folder. Substitute the three placeholders, then drop the suffix:

```bash
sed -e 's/<package_name>/aws_foo/g' -e 's/<PACKAGE_NAME>/AWS_FOO/g' -e 's/<package-name>/aws-foo/g' \
    templates/package-tests/mock_aws.py.tmpl > aws_foo/tests/mock_aws.py
```

## What the agent does

1. **Read the project**: `pyproject.toml`, `mise.toml`, `.mise/tasks/`, `.github/workflows/`, the package's `tests/` subpackage, `CLAUDE.md`. Note which AWS services the library calls and what already exists; merge, do not overwrite a file that already holds other things.
2. **Copy and substitute** every template from the file map.
3. **Write the service layer.** The templates contain one worked example, S3 (two buckets, one with versioning), in blocks marked `SERVICE LAYER`. Replace it with what this library needs; it can span several services. Answer these questions from the library's own features, and keep the answers consistent across `aws_ci.py`, `setup-aws-ci.py` and `mock_aws.py`:
   1. Which shared, long-lived resources do the tests need? `setup-aws-ci.py` creates each one if missing, idempotently (one `ensure_xxx()` per resource).
   2. Which IAM statements does the test user need? Only the shared resources, the `<package-name>-test-tmp-*` resources, the few account-level actions the tests call, and `sts:GetCallerIdentity`.
   3. What does `BaseTest._setup_aws` create in moto so that a moto test sees the same world as a real AWS test?
   4. How does a real AWS test class empty its own isolation prefix (or name prefix) when it starts?
   5. **Lifecycle management**: how does what the tests leave behind expire on its own (for S3, a bucket lifecycle rule on `projects/<package_name>/unittest/`), so that a failed run never leaves cost behind?
   Moto must support every call the tests make; check that before relying on a service.
4. **Wire up**: `pyproject.toml` extras (`test`: pytest, pytest-cov, moto; `mise`: PyGithub), `mise.toml` env and tasks, `.coveragerc`, CI workflow (set `PACKAGE_NAME` and the Python matrix), `CLAUDE.md` sections.
5. **Convert the test modules that call AWS** to the mixin shape of `test_example_module.py.tmpl`: one mixin with `module = "..."`, `TestMock` and `TestRealAws`, each test under `self.prefix_test`.
6. **Verify offline**: `mise run cov` (or `.venv/bin/pytest tests`) must pass, including `tests/tests/test_tests_mock_aws.py`; its subprocess tests import the package, so the package must be installed in the venv (`uv sync` does it). Every `TestRealAws` class must show as skipped with the reason `set <PACKAGE_NAME>_TEST_REAL_AWS=true to run it`.
7. **Hand over** the list below to the developer. Never run `setup-aws-ci`, `teardown-aws-ci` or `cov-aws` yourself unless the developer asks: they use the developer's AWS account and GitHub token.

## What the developer does (once per project)

1. In the AWS console, create (or reuse) a powerful IAM user that can create the resources and IAM users, create an access key, and define the profile `project_<package_name>_dev` in `~/.aws/config` and `~/.aws/credentials`. `mise run setup-aws-ci` prints the exact snippet when the profile is missing.
2. Make `GITHUB_TOKEN` available in `mise.toml` `[env]` (a token that can write the repository's Actions secrets).
3. `mise run inst`, then `mise run setup-aws-ci`. It creates the resources, the IAM user `project-<package-name>-test`, its access key, the two GitHub secrets, and prints the `project_<package_name>_test` profile.
4. Paste the printed profile into `~/.aws/config` and `~/.aws/credentials`. The secret key is only shown once.
5. `mise run cov-aws`: the `TestRealAws` classes now run.
6. Optional: `mise run docs-run` to execute the notebooks.
7. Push to `main` or `dev`: CI runs moto and real AWS in every job.
8. Keep an AWS Budgets alert on the account.

Later operations:

- `mise run setup-aws-ci` again: idempotent; it only refreshes the IAM policy when the user exists (e.g. after a new service was added).
- `mise run setup-aws-ci -- --force`: delete the user and the secrets, then recreate them with a new access key (key rotation, or a previous run that failed halfway).
- `mise run teardown-aws-ci`: delete the user and the secrets; the shared resources are kept.

## Invariants (do not break them when adapting)

- The switch accepts only unset, `true`, `false`; anything else is an error. With `true`, missing credentials are an error, never a skip.
- `TestMock` always runs; `TestRealAws` runs only when the test allows it (not `@mock_only`) AND the run allows it (`<PACKAGE_NAME>_TEST_REAL_AWS=true`).
- A moto session always has fake credentials, so a moto test can never reach a real profile.
- On CI (`CI` set) the credentials come from the two `*_FOR_GITHUB_CI` env vars; locally from the test profile. The dev profile is only used by the setup / teardown tasks.
- Each run, OS and Python version writes under its own prefix; each class under `module`; each test under its own folder. A real AWS class empties its own prefix when it starts.
- `setup_class` stops moto if setup fails; `custom_teardown_class` runs before moto stops.
- Names and prefixes appear in both `aws_ci.py` and `mock_aws.py`, each marked "Keep in sync"; change both together.
- CI uses uv, not mise: the `[env]` of `mise.toml` reads local secrets that the runners do not have.
- The notebooks never contain a profile name, an account id or a secret; `docs-run` redacts the account id and fails if it is still there.
