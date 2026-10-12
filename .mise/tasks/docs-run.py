# -*- coding: utf-8 -*-

"""
Execute the documentation notebooks against real AWS, then hide the AWS
account id in the saved files.

Usage::

    # all notebooks under docs/source, in chapter order
    mise run docs-run
    # only some notebooks
    mise run docs-run -- docs/source/01-Quick-Start/index.ipynb

Steps:

1. Get the account id of the profile ``S3PATHLIB_TEST_AWS_PROFILE`` (set by
   ``mise.toml``); the notebooks build the CI bucket names from it.
2. Execute each notebook in its own folder and save it in place, also when a
   cell fails, so the error can be read in the notebook.
3. Replace the account id with ``123456789012`` in the saved file.
4. Scan every notebook under ``docs/source``; fail if the real account id is
   still there.

Read the Docs has no credentials and never executes the notebooks
(``nbsphinx_execute = "never"``), so the committed outputs come from here.
"""

import os
import sys
from pathlib import Path

import boto3
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

ENV_TEST_AWS_PROFILE = "S3PATHLIB_TEST_AWS_PROFILE"
FAKE_AWS_ACCOUNT_ID = "123456789012"
TIMEOUT = 600  # seconds per cell

dir_project_root = Path(__file__).absolute().parent.parent.parent
dir_docs_source = dir_project_root / "docs" / "source"


def get_aws_account_id() -> str:
    profile = os.environ.get(ENV_TEST_AWS_PROFILE)
    if profile is None:
        raise SystemExit(f"{ENV_TEST_AWS_PROFILE} is not set; run it with mise")
    boto_ses = boto3.Session(profile_name=profile)
    return boto_ses.client("sts").get_caller_identity()["Account"]


def find_notebooks() -> list[Path]:
    paths = list()
    for path in sorted(dir_docs_source.glob("**/*.ipynb")):
        if ".ipynb_checkpoints" in path.parts:
            continue
        paths.append(path)
    return paths


def save_redacted(nb: nbformat.NotebookNode, path: Path, aws_account_id: str):
    # redact before writing, so the real id never reaches the disk
    text = nbformat.writes(nb) + "\n"
    text = text.replace(aws_account_id, FAKE_AWS_ACCOUNT_ID)
    path.write_text(text, encoding="utf-8")


def run_notebook(path: Path, aws_account_id: str) -> bool:
    print(f"Execute {path} ...", flush=True)
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=TIMEOUT,
        kernel_name="python3",
        # no timestamps in the cell metadata, so a rerun gives no diff
        record_timing=False,
        resources={"metadata": {"path": str(path.parent)}},
    )
    try:
        client.execute()
        ok = True
    except CellExecutionError as e:
        print(e, file=sys.stderr)
        ok = False
    # Save even when a cell fails: the error output is what we want to read.
    save_redacted(nb, path, aws_account_id)
    if ok:
        print("  ok")
    else:
        print("  FAILED (saved with the error output)")
    return ok


def check_no_account_id(aws_account_id: str) -> list[Path]:
    leaked = list()
    for path in find_notebooks():
        if aws_account_id in path.read_text(encoding="utf-8"):
            leaked.append(path)
    return leaked


def main():
    aws_account_id = get_aws_account_id()
    if len(sys.argv) > 1:
        paths = [Path(arg).absolute() for arg in sys.argv[1:]]
    else:
        paths = find_notebooks()

    failed = list()
    for path in paths:
        if run_notebook(path, aws_account_id) is False:
            failed.append(path)

    leaked = check_no_account_id(aws_account_id)
    for path in leaked:
        print(f"ERROR: the real AWS account id is in {path}", file=sys.stderr)
    for path in failed:
        print(f"ERROR: a cell failed in {path}", file=sys.stderr)
    if len(failed) > 0 or len(leaked) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
