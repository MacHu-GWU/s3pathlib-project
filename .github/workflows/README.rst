How to test this in CI
==============================================================================
The unit tests can run against real AWS (test classes with ``use_mock = False``). They need two S3 buckets, an IAM user that can use them, and the access key of that user in the GitHub Actions secrets. Two idempotent mise tasks manage all of this (code in ``.mise/tasks/aws_ci.py``):

.. code-block:: bash

    # create the buckets and the IAM user, set the GitHub secrets,
    # and print the local profile to paste into ~/.aws
    mise run setup-aws-ci

    # the IAM user exists but the GitHub secrets were not set:
    # delete the user and the secrets, then create them again
    mise run setup-aws-ci -- --force

    # delete the IAM user and the GitHub secrets (keeps the buckets)
    mise run teardown-aws-ci

The AWS profiles are defined in the ``[env]`` section of ``mise.toml``:

- ``S3PATHLIB_DEV_AWS_PROFILE`` (``project_s3pathlib_dev``): a powerful profile that can create S3 buckets and IAM users. The tasks run with it. Create it yourself; the tasks print what to paste into ``~/.aws`` when it is missing.
- ``S3PATHLIB_TEST_AWS_PROFILE`` (``project_s3pathlib_test``): the profile of the test IAM user. ``s3pathlib/tests/mock_aws.py`` uses it to run the tests locally against real AWS. ``mise run setup-aws-ci`` prints it after creating the user.

Resources (``${aws_account_id}`` is the account of the dev profile):

- Buckets ``${aws_account_id}-us-east-1-s3pathlib-test`` (versioning off) and ``${aws_account_id}-us-east-1-s3pathlib-test-versioning-on`` (versioning on).
- IAM user ``project-s3pathlib-test`` with the inline policy ``s3pathlib-unit-test``: full access to the two buckets, create / delete / inspect any bucket (``tests/core/test_core_bucket.py`` uses temporary buckets), and ``sts:GetCallerIdentity``.
- GitHub Actions secrets ``AWS_ACCESS_KEY_ID_FOR_GITHUB_CI`` and ``AWS_SECRET_ACCESS_KEY_FOR_GITHUB_CI``, read by ``main.yml``.
- Bucket lifecycle rule: everything under ``projects/s3pathlib/unittest/`` expires after one day.


The CI workflow (``main.yml``)
------------------------------------------------------------------------------
- Runs on every push to ``main`` and ``dev``, and by hand (``workflow_dispatch``).
- Matrix: Ubuntu with Python 3.11, 3.12, 3.13 and 3.14; Windows with Python 3.14 only.
- Every job runs the whole test suite against moto **and** real AWS (``S3PATHLIB_TEST_REAL_AWS=true``, with the secrets above). Without the secrets the real AWS tests fail; they are never skipped silently.
- Each workflow run writes to its own S3 folder, ``projects/s3pathlib/unittest/ci/${GITHUB_RUN_ID}/...`` (see ``get_root_prefix`` in ``s3pathlib/tests/mock_aws.py``), so runs of different pushes can run at the same time; the lifecycle rule deletes the folders.
- It uses uv only, not mise: the ``[env]`` section of ``mise.toml`` reads local secrets that do not exist on the runners.
- The ``S3Path.sync`` end-to-end tests use the AWS CLI preinstalled on the GitHub-hosted runners.
- The Ubuntu jobs upload the coverage to Codecov (secret ``CODECOV_TOKEN``, set by ``mise run setup-codecov``).
