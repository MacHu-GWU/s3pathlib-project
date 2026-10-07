# -*- coding: utf-8 -*-

"""
Create the AWS test environment of s3pathlib (idempotent).

1. Create the two test buckets if missing, enable versioning on the second,
   and make the unit test objects expire after one day (lifecycle rule).
2. Create the test IAM user with its inline policy and an access key.
3. Store the access key in the GitHub Actions secrets.
4. Print the ``~/.aws`` profile to paste, for running the tests locally.

If the IAM user already exists, only its inline policy is updated, and the
access key steps are skipped: the secret access key can only be read when it is
created. Pass ``--force`` to delete the
user and the secrets first and create them again, e.g. when a previous run
created the user but failed to set the GitHub secrets.

Usage::

    mise run setup-aws-ci
    mise run setup-aws-ci -- --force

See ``aws_ci.py`` for the resources and the profiles.
"""

import argparse
import json

from aws_ci import AWS_REGION
from aws_ci import ENV_TEST_AWS_PROFILE
from aws_ci import GITHUB_SECRET_ACCESS_KEY_ID
from aws_ci import GITHUB_SECRET_SECRET_ACCESS_KEY
from aws_ci import IAM_POLICY_NAME
from aws_ci import IAM_USER_NAME
from aws_ci import UNIT_TEST_PREFIX
from aws_ci import build_iam_policy
from aws_ci import build_lifecycle_configuration
from aws_ci import delete_github_secrets
from aws_ci import delete_iam_user
from aws_ci import get_bucket
from aws_ci import get_bucket_console_url
from aws_ci import get_bucket_with_versioning
from aws_ci import get_dev_boto_session
from aws_ci import get_env
from aws_ci import get_github_repo
from aws_ci import get_github_secrets_url
from aws_ci import get_iam_user_console_url
from aws_ci import is_iam_user_exists
from aws_ci import print_caller_identity
from aws_ci import print_json
from aws_ci import print_profile_snippet


def ensure_bucket(s3_client, bucket: str, versioning: bool):
    """
    Create the bucket if missing. Enable versioning when ``versioning`` is
    True. Versioning can never be turned off once enabled, so a regular bucket
    with versioning only gets a warning.
    """
    print(f"Bucket {bucket} ({get_bucket_console_url(bucket)}):")
    try:
        s3_client.head_bucket(Bucket=bucket)
        print("  already exists")
    except s3_client.exceptions.ClientError as e:
        if e.response["Error"]["Code"] in ["404", "NoSuchBucket"]:
            kwargs = dict(Bucket=bucket)
            if AWS_REGION != "us-east-1":
                kwargs["CreateBucketConfiguration"] = dict(
                    LocationConstraint=AWS_REGION,
                )
            s3_client.create_bucket(**kwargs)
            print("  created")
        else:
            raise e

    res = s3_client.get_bucket_versioning(Bucket=bucket)
    status = res.get("Status")
    if versioning:
        if status == "Enabled":
            print("  versioning is enabled")
        else:
            s3_client.put_bucket_versioning(
                Bucket=bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )
            print("  enabled versioning")
    else:
        if status is None:
            print("  versioning is off")
        else:
            print(f"  WARNING: versioning is {status}, expected off")

    # replaces the whole lifecycle configuration; these buckets only hold tests
    s3_client.put_bucket_lifecycle_configuration(
        Bucket=bucket,
        LifecycleConfiguration=build_lifecycle_configuration(),
    )
    print(f"  lifecycle: objects under {UNIT_TEST_PREFIX} expire after 1 day")


def put_iam_policy(iam_client, aws_account_id: str):
    """
    Put (create or replace) the inline policy of the IAM user. Idempotent.
    """
    policy = build_iam_policy(aws_account_id)
    iam_client.put_user_policy(
        UserName=IAM_USER_NAME,
        PolicyName=IAM_POLICY_NAME,
        PolicyDocument=json.dumps(policy),
    )
    print(f"  put inline policy {IAM_POLICY_NAME}:")
    print_json(policy)


def create_iam_user(iam_client, aws_account_id: str) -> dict:
    """
    Create the IAM user, put its inline policy, and return a new access key.
    """
    print(f"Create IAM user {IAM_USER_NAME} ({get_iam_user_console_url(IAM_USER_NAME)}):")
    iam_client.create_user(UserName=IAM_USER_NAME)
    print("  created user")

    put_iam_policy(iam_client, aws_account_id)

    res = iam_client.create_access_key(UserName=IAM_USER_NAME)
    access_key = res["AccessKey"]
    print(f"  created access key {access_key['AccessKeyId']}")
    return access_key


def set_github_secrets(access_key: dict):
    print(f"Set GitHub Actions secrets ({get_github_secrets_url()}):")
    repo = get_github_repo()
    repo.create_secret(
        secret_name=GITHUB_SECRET_ACCESS_KEY_ID,
        unencrypted_value=access_key["AccessKeyId"],
        secret_type="actions",
    )
    print(f"  set secret {GITHUB_SECRET_ACCESS_KEY_ID}")
    repo.create_secret(
        secret_name=GITHUB_SECRET_SECRET_ACCESS_KEY,
        unencrypted_value=access_key["SecretAccessKey"],
        secret_type="actions",
    )
    print(f"  set secret {GITHUB_SECRET_SECRET_ACCESS_KEY}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help="delete the IAM user and the GitHub secrets first, then create them again",
    )
    args = parser.parse_args()

    test_profile = get_env(ENV_TEST_AWS_PROFILE)
    boto_ses = get_dev_boto_session()
    aws_account_id = print_caller_identity(boto_ses)
    print()

    s3_client = boto_ses.client("s3")
    ensure_bucket(s3_client, get_bucket(aws_account_id), versioning=False)
    ensure_bucket(s3_client, get_bucket_with_versioning(aws_account_id), versioning=True)
    print()

    iam_client = boto_ses.client("iam")
    if is_iam_user_exists(iam_client, IAM_USER_NAME):
        if args.force:
            print("--force: delete the existing IAM user and GitHub secrets first")
            delete_github_secrets()
            delete_iam_user(iam_client, IAM_USER_NAME)
            print()
        else:
            print(f"IAM user {IAM_USER_NAME} already exists, skip creating it.")
            print(f"  {get_iam_user_console_url(IAM_USER_NAME)}")
            # the policy is not a secret: keep it up to date
            put_iam_policy(iam_client, aws_account_id)
            print(
                "The access key, the GitHub secrets and the local profile are "
                "not touched. Run with --force to recreate the user and its "
                "access key."
            )
            return

    access_key = create_iam_user(iam_client, aws_account_id)
    print()
    set_github_secrets(access_key)
    print()
    print_profile_snippet(
        profile=test_profile,
        aws_access_key_id=access_key["AccessKeyId"],
        aws_secret_access_key=access_key["SecretAccessKey"],
    )
    print("Done.")


if __name__ == "__main__":
    main()
