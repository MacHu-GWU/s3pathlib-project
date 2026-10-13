#!/usr/bin/env python3
"""
Tests of ``scan.py``. Standard library only; run them with::

    python test_scan.py

Test order: the 2.x fixture (every rule, nothing else), 3.x code (no
finding), the cases a rule must not report, notebooks, the command line.
"""

from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from pathlib import Path

DIR_HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(DIR_HERE))

import scan  # noqa: E402

PATH_FIXTURE = DIR_HERE / "fixture_2x.py"

# 3.x code that uses the same features as the fixture
CODE_3X = """
import hashlib

import boto3
from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.api import better_client
from s3pathlib.api import exc
from s3pathlib import utils
from s3pathlib.aws import S3Context
from s3pathlib.marker import deprecated
from s3pathlib.tests.mock_aws import BaseTest

boto_ses = boto3.Session()
s3_context.attach_s3_client(boto_ses.client("s3"))
s3_client = s3_context.s3_client

p = S3Path("bucket", "folder", "file.txt")
p.read_text(s3_client=s3_client)
p.delete(checksum_algorithm="CRC32")
print(p.get_console_url(region="us-east-1", partition="aws-us-gov"))
p.delete()
result = better_client.paginate_list_objects_v2(s3_client, "bucket", "prefix/")
for dct in result.common_prefixes():
    print(dct)
digest = hashlib.md5(b"data").hexdigest()
with p.open("r", compression="disable") as f:
    print(f.read())
with p.open("w", if_none_match="*", multipart_upload=False) as f:
    f.write("x")
for csv in S3Path("bucket", "folder/").iter_objects().filter_by_ext(".csv", ""):
    print(csv)
better_client.delete_object_versions(s3_client, "bucket", prefix="data/")
data = p.read_bytes(range="bytes=0-9")
p.copy_file(S3Path("bucket", "copy.txt"), overwrite=True)

try:
    p.copy_file(S3Path("bucket", "copy.txt"))
except exc.S3FileNotExist:
    pass

new = S3Path("bucket") / "folder/" / "file.txt"
new = S3Path("bucket", "folder/").joinpath("file.txt")
new = S3Path("bucket").joinpath("folder", "file.txt")
new = S3Path("bucket") / ["folder", "file.txt"]
new = S3Path("s3://bucket/folder/") / "file.txt"
new = S3Path("bucket") / "file.txt"
rel = new.relative_to(S3Path("bucket", "folder/"))


class Test(BaseTest):
    def test_something(self):
        print(self.s3_client)
"""


def expected_from_comments(text: str) -> set[tuple[int, str]]:
    """
    ``(line, rule id)`` from the ``# M04`` / ``# M06, S10`` comments of the
    fixture.
    """
    expected = set()
    for number, line in enumerate(text.splitlines(), start=1):
        match = re.search(r"#\s*([A-Z]\d\d(?:\s*,\s*[A-Z]\d\d)*)\s*$", line)
        if match is not None:
            for rule_id in re.split(r"\s*,\s*", match.group(1)):
                expected.add((number, rule_id))
    return expected


def rule_ids(findings: list[scan.Finding]) -> set[str]:
    result = set()
    for f in findings:
        result.add(f.rule_id)
    return result


class TestFixture(unittest.TestCase):
    def test_each_line_hits_exactly_its_rules(self):
        """
        Every rule the comment of a line names is found on that line, and
        nothing else is found anywhere: no rule is missed, none is noise.
        """
        text = PATH_FIXTURE.read_text(encoding="utf-8")
        findings = scan.scan_source(text, "fixture_2x.py")
        found = set()
        for f in findings:
            found.add((f.line, f.rule_id))
        self.assertEqual(found, expected_from_comments(text))

    def test_every_rule_is_in_the_fixture(self):
        """
        A new rule must come with a line of the fixture that hits it.
        """
        text = PATH_FIXTURE.read_text(encoding="utf-8")
        found = rule_ids(scan.scan_source(text, "fixture_2x.py"))
        self.assertEqual(found, set(scan.RULES_BY_ID))

    def test_category_comes_from_the_rule(self):
        text = PATH_FIXTURE.read_text(encoding="utf-8")
        for f in scan.scan_source(text, "fixture_2x.py"):
            self.assertEqual(f.category, scan.RULES_BY_ID[f.rule_id].category)


class TestNoFalsePositive(unittest.TestCase):
    def test_3x_code(self):
        """
        Code written for 3.x gives no finding.
        """
        findings = scan.scan_source(textwrap.dedent(CODE_3X), "code_3x.py")
        self.assertEqual(findings, [])

    def test_literal_paths(self):
        """
        A bucket alone and a folder are not files; a non literal path is
        unknown and not reported.
        """
        for code in [
            'S3Path("bucket") / "x"',
            'S3Path("bucket/") / "x"',
            'S3Path("s3://bucket") / "x"',
            'S3Path("bucket", "folder/") / "x"',
            "S3Path(name) / 'x'",
            'S3Path("arn:aws:s3:::bucket/key") / "x"',
            'make_path() / "folder/" / "x"',
            'Path("/tmp") / "logs" / "1.log"',
            'dir_local / "logs" / "1.log"',
            'self.root / "logs" / "1.log"',
        ]:
            with self.subTest(code=code):
                self.assertEqual(scan.scan_source(code, "x.py"), [])

    def test_literal_file_paths(self):
        for code in [
            'S3Path("bucket/folder") / "x"',
            'S3Path("s3://bucket/folder") / "x"',
            'S3Path("bucket", "folder") / "x"',
            'S3Path("bucket", "folder", "") / "a" / "b"',
        ]:
            with self.subTest(code=code):
                self.assertEqual(rule_ids(scan.scan_source(code, "x.py")), {"D01"})

    def test_condition_with_multipart_false(self):
        code = 'p.open("w", if_match="e", multipart_upload=False)'
        self.assertEqual(scan.scan_source(code, "x.py"), [])

    def test_hard_delete_without_version_id(self):
        code = "p.delete(is_hard_delete=True)"
        self.assertEqual(scan.scan_source(code, "x.py"), [])

    def test_except_without_matching_call(self):
        """
        ``except ClientError`` around a call whose exception did not change.
        """
        code = textwrap.dedent(
            """
            try:
                p.read_text()
            except ClientError:
                pass
            """
        )
        self.assertEqual(scan.scan_source(code, "x.py"), [])


class TestPaths(unittest.TestCase):
    def write(self, root: Path, name: str, text: str) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_folder_skips_unrelated_and_venv(self):
        """
        Files that do not mention s3pathlib, and virtualenv folders, are not
        scanned; a syntax error is an error, not a crash.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "app.py", "from s3pathlib import S3Path\n")
            self.write(root, "other.py", "f(bsm=1)\n")
            self.write(
                root, ".venv/lib/s3pathlib/x.py", "from s3pathlib import S3Path\n"
            )
            self.write(root, "broken.py", "import s3pathlib\ndef (:\n")
            findings, errors = scan.scan_path(root)
        self.assertEqual(
            [(Path(f.location).name, f.rule_id) for f in findings], [("app.py", "M01")]
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("broken.py", errors[0])

    def test_notebook(self):
        """
        Code cells are scanned with their cell number and line; magics are
        ignored; markdown cells are not code.
        """
        notebook = {
            "cells": [
                {"cell_type": "markdown", "source": ["from s3pathlib import S3Path"]},
                {
                    "cell_type": "code",
                    "source": [
                        "%load_ext autoreload\n",
                        "import os\n",
                        "from s3pathlib import S3Path\n",
                    ],
                },
                {"cell_type": "code", "source": "p.read_text(bsm=client)"},
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "demo.ipynb", json.dumps(notebook))
            findings, errors = scan.scan_path(path)
        self.assertEqual(errors, [])
        result = list()
        for f in findings:
            result.append((f.location.split("[")[1], f.line, f.rule_id))
        self.assertEqual(sorted(result), [("cell 2]", 3, "M01"), ("cell 3]", 1, "M04")])


class TestCommandLine(unittest.TestCase):
    def run_main(self, argv: list[str]) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = scan.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_text(self):
        code, out, _ = self.run_main(["--path", str(PATH_FIXTURE)])
        self.assertEqual(code, 0)
        self.assertIn(": M04 [mechanical] ", out)
        self.assertRegex(
            out.splitlines()[-1],
            r"^\d+ findings: \d+ mechanical, \d+ semantic, \d+ deprecated$",
        )

    def test_json(self):
        code, out, _ = self.run_main(["--path", str(PATH_FIXTURE), "--as_json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["errors"], [])
        self.assertEqual(
            set(data["findings"][0]),
            {"location", "line", "col", "rule_id", "category", "message"},
        )

    def test_list_rules(self):
        code, out, _ = self.run_main(["--list_rules"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), len(scan.RULES))

    def test_missing_path(self):
        code, _, err = self.run_main(["--path", "/does/not/exist"])
        self.assertEqual(code, 1)
        self.assertIn("does not exist", err)

    def test_no_path(self):
        code, _, err = self.run_main([])
        self.assertEqual(code, 1)
        self.assertIn("--path is required", err)


if __name__ == "__main__":
    unittest.main()
