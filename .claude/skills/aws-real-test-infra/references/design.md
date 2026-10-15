# Design notes

One short heading per decision, then the reason. Read this before changing a template.

## Two profiles, two jobs

The dev profile is powerful (it creates resources and IAM users) and is only used by `setup-aws-ci` / `teardown-aws-ci`, run by hand. The test profile belongs to an IAM user that can only touch the test resources; tests and notebooks use it, locally and on CI. A buggy or looping test can at worst damage the test resources, never the account.

## The profile names live in mise.toml

`[env]` of `mise.toml` is the single place that names the profiles. The tasks, `mock_aws.py` and `docs-run.py` read the environment variables, so no script hard-codes a profile, and running outside `mise` fails with a clear message instead of picking up a default profile.

## A static access key in GitHub secrets, not OIDC

The test user's access key goes into two repository secrets. It keeps the setup to one IAM user and two secrets, with nothing else in the account to maintain, and isolates the project: each library has its own user that can only reach its own resources. The secret key is only readable when it is created, so the setup prints it once for the local profile and writes it to GitHub in the same run.

## Idempotent boto3 scripts, not CDK or CloudFormation

The resources are few and simple. A plain script that checks, creates if missing and updates the policy can be read top to bottom, runs with the project's own venv, needs no bootstrap stack, and is safe to rerun. `--force` covers the one non-idempotent part, the access key.

## The IAM policy is built in code

`build_iam_policy(aws_account_id)` puts the account-specific resource ARNs into the policy, and rerunning the setup refreshes it. No JSON file to keep in sync by hand.

## Temporary resources share one name prefix

Tests that create and delete resources (e.g. buckets) name them `<package-name>-test-tmp-{uuid}`. The policy grants full access to that prefix only, so destructive tests never run on the shared resources, and leftovers are easy to recognize.

## One switch with three allowed values

`<PACKAGE_NAME>_TEST_REAL_AWS` is unset, `true` or `false`; a typo is an error. With `true`, missing credentials are an error. A run that asked for real AWS must never look green after silently skipping it.

## Both the test and the run must allow real AWS

A test opts out with `@mock_only("reason")`, a run opts in with the switch. Neither overrides the other, so `mise run cov` never costs anything and `@mock_only` tests never reach AWS.

## Write a test once, run it twice

The logic lives in a mixin; `TestMock` and `TestRealAws` are one-line subclasses. Every behavior is checked against moto (fast, free, always) and against AWS (the truth), and a difference between the two shows up as a failure in one class only.

## Fake credentials for moto

The moto session has the credentials `testing` / `testing`, so a moto test can never use a real profile from the environment, even when moto does not intercept a call.

## Isolation by prefix, per run, OS and Python version

The prefix contains `local` or `ci/<GITHUB_RUN_ID>`, `sys.platform` and the Python version, then the module, then the test name. The 8 CI jobs and two pushes at the same time never share a folder, so a class can empty its own folder when it starts without hurting another run.

## Clean at the start, expire with a lifecycle rule

A real AWS class deletes its own prefix (all versions) when it starts, so it never sees leftovers of a previous run. Nothing is cleaned at the end, so the data of a failed run can still be inspected; the lifecycle rule (1 day) deletes it. Each service has its own way to expire data; deciding how is part of the service layer.

## Verify with native boto3 calls

A test checks AWS state with plain boto3 calls, not with the library under test, so a bug in the library cannot hide itself.

## setup_class stops moto when it fails

pytest does not call `teardown_class` when `setup_class` raises. A mock left running would make the next classes talk to moto by accident, so `setup_class` stops it itself. `custom_teardown_class` runs before moto stops, so it talks to the same backend as the tests.

## The framework has its own tests

`test_tests_mock_aws.py` tests the switch, the prefixes, the credential errors and the class life cycle, and runs pytest in a subprocess on a generated file to check which tests run for each switch value. The rules above are easy to break by accident; these tests catch it.

## mock_aws.py ships in the package

`<package_name>/tests/mock_aws.py` is importable (`from <package_name>.tests.mock_aws import BaseTest`), so every test module and the framework tests share one implementation. The setup task cannot import it (it lives outside the package), so the names that both need are duplicated and marked "Keep in sync".

## CI uses uv, not mise

`mise.toml` `[env]` calls local secret tools that do not exist on the runners. The workflow installs with `uv sync --frozen --extra test` and sets the switch and the two secrets itself.

## Real AWS in every CI job

Every job of the matrix (OS x Python) runs the real AWS tests. A job sends a few thousand requests: cents per push. The real risk is a test that loops, which the narrow IAM policy and a Budgets alert cover.

## Notebooks run against AWS, outputs committed

Read the Docs has no credentials, so the notebooks are executed locally by `docs-run` with the test profile and their outputs committed (`nbsphinx_execute = "never"`). Resource names contain the account id, so `docs-run` replaces it with `123456789012` before writing to disk and fails if the real one is still in any notebook. Each notebook empties its own prefix first, so a rerun gives no diff.
