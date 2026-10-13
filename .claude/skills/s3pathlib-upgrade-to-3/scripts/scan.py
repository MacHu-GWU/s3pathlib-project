#!/usr/bin/env python3
"""
Find the code that needs a change to upgrade from s3pathlib 2.x to 3.x.

It parses Python files and the code cells of Jupyter notebooks with ``ast``
and reports each finding with its location, a rule id and a category:

- ``mechanical``: a rename or a removed name with a direct replacement; safe
  to rewrite.
- ``semantic``: the behavior changed; read the code around it and decide.
- ``deprecated``: still works in 3.x with a DeprecationWarning, breaks in 4.0.

The rule ids match the sections of ``references/migration.md``. Only the files
that mention ``s3pathlib`` or ``S3Path`` are scanned, so a ``bsm=`` argument of
another library is not reported. Static analysis cannot know the type of every
object: a ``semantic`` finding on a method name (``.iterdir()``,
``.delete()``) may be on an object that is not an ``S3Path``.

Usage::

    python scan.py --path /path/to/project
    python scan.py --path /path/to/project --as_json
    python scan.py --list_rules
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import sys
from pathlib import Path

MECHANICAL = "mechanical"
SEMANTIC = "semantic"
DEPRECATED = "deprecated"


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    category: str
    title: str


RULES = [
    Rule("M01", MECHANICAL, "top level import: use 'from s3pathlib.api import ...'"),
    Rule(
        "M02", MECHANICAL, "'context' is now 's3_context' and only holds the S3 client"
    ),
    Rule("M03", MECHANICAL, "'s3pathlib.aws.Context' is now 'S3Context'"),
    Rule(
        "M04", MECHANICAL, "'bsm=' is now 's3_client=' and takes a boto3 S3 client only"
    ),
    Rule("M05", MECHANICAL, "'check_sum_algorithm=' is now 'checksum_algorithm='"),
    Rule("M06", MECHANICAL, "'quite=' is now 'quiet=' (deprecated in 3.x)"),
    Rule(
        "M07",
        MECHANICAL,
        "removed console URL API: use 'get_console_url(region=..., partition=...)'",
    ),
    Rule("M08", MECHANICAL, "'delete_if_exists()' is removed: use 'delete()'"),
    Rule("M09", MECHANICAL, "'common_prefixs' is now 'common_prefixes'"),
    Rule(
        "M10",
        MECHANICAL,
        "hash helpers of 's3pathlib.utils' are removed: use 'hashlib'",
    ),
    Rule(
        "M11",
        MECHANICAL,
        "old deprecation helpers are removed: use 's3pathlib.marker.deprecated'",
    ),
    Rule("M12", MECHANICAL, "'s3pathlib.compat' is removed"),
    Rule(
        "M13",
        MECHANICAL,
        "better_client function: use 's3pathlib.api.better_client.<name>'",
    ),
    Rule("M14", MECHANICAL, "removed or renamed name of 's3pathlib.exc'"),
    Rule(
        "M15",
        MECHANICAL,
        "'open(ignore_ext=...)' is removed: use 'compression=\"disable\"'",
    ),
    Rule(
        "M16",
        MECHANICAL,
        "test helper 's3pathlib.tests.mock' is now 's3pathlib.tests.mock_aws'",
    ),
    Rule(
        "M17",
        MECHANICAL,
        "'func_args.NOTHING' is not used any more: leave the argument out",
    ),
    Rule("M18", MECHANICAL, "removed name of 's3pathlib.validate'"),
    Rule(
        "M19",
        MECHANICAL,
        "'update_metadata()' is removed: copy the object onto itself with 'metadata='",
    ),
    Rule(
        "S01",
        SEMANTIC,
        "return value changed: 'copy_file' and 'delete' return a new S3Path",
    ),
    Rule(
        "S02", SEMANTIC, "'iterdir()' yields files and folders mixed, in S3 key order"
    ),
    Rule(
        "S03",
        SEMANTIC,
        "'delete(version_id=..., is_hard_delete=True)' now raises ValueError",
    ),
    Rule("S04", SEMANTIC, "exception type changed for this call"),
    Rule("S05", SEMANTIC, "'filter_by_ext' needs extensions with a leading dot"),
    Rule(
        "S06",
        SEMANTIC,
        "'open(range=...)' / 'part_number=' never had an effect: use 'read_bytes(range=...)'",
    ),
    Rule(
        "S07",
        SEMANTIC,
        "'open(if_match=...)' / 'if_none_match=' needs 'multipart_upload=False'",
    ),
    Rule(
        "S08",
        SEMANTIC,
        "'metadata' / 'response' return a copy: changing it changes nothing",
    ),
    Rule("S09", SEMANTIC, "'delete_object_versions(prefix=...)' needs a folder prefix"),
    Rule("S10", SEMANTIC, "sync uses the identity of the S3 client, not AWS_PROFILE"),
    Rule("S11", SEMANTIC, "test base class: 'cls.bsm' is gone, use 'self.s3_client'"),
    Rule(
        "D01",
        DEPRECATED,
        "joining onto a file (no trailing '/'): deprecated, raises in 4.0",
    ),
    Rule(
        "D02",
        DEPRECATED,
        "'relative_to' a file (no trailing '/'): deprecated, raises in 4.0",
    ),
]
RULES_BY_ID = {rule.id: rule for rule in RULES}

# names that 2.x exported from the top level ``s3pathlib``
TOP_LEVEL_NAMES = {
    "S3Path",
    "ContentTypeEnum",
    "validate_s3_bucket",
    "validate_s3_key",
    "validate_s3_uri",
    "validate_s3_arn",
    "and_",
    "or_",
    "not_",
}
# the functions of ``better_client``, which 2.x exposed as ``s3pathlib.api.*``
BETTER_CLIENT_NAMES = {
    "is_bucket_exists",
    "head_object",
    "is_object_exists",
    "update_bucket_tagging",
    "update_object_tagging",
    "upload_dir",
    "paginate_list_objects_v2",
    "is_content_an_object",
    "calculate_total_size",
    "count_objects",
    "paginate_list_object_versions",
    "delete_object",
    "delete_dir",
    "delete_object_versions",
}
CONTEXT_ATTRS = {
    "attach_boto_session",
    "attach_sts_client",
    "aws_account_id",
    "aws_region",
    "boto_ses",
    "sts_client",
}
CONSOLE_URL_ATTRS = {
    "get_regional_console_url",
    "us_gov_cloud_console_url",
    "get_regional_us_gov_cloud_console_url",
    "s3_select_console_url",
    "get_regional_s3_select_console_url",
    "s3_select_us_gov_cloud_console_url",
    "get_regional_s3_select_us_gov_cloud_console_url",
    "make_s3_select_console_url",
}
HASH_NAMES = {"md5_binary", "sha256_binary", "hash_binary", "hash_file"}
MARKER_NAMES = {"deprecate_v1", "deprecate_v2", "warn_deprecate", "warn_beta"}
EXC_NAMES = {"_S3PathTypeError", "ensure_one_and_only_one_not_none", "ensure_all_none"}
VALIDATE_NAMES = {
    "valid_bucket_charset",
    "letter_and_number",
    "safe_key_charset",
    "req_special_handling_key_charset",
    "to_avoid_key_charset",
    "valid_key_charset",
    "S3BucketValidationError",
    "S3KeyValidationError",
}
# (exception caught in 2.x, methods called in the try block) -> what 3.x raises
EXCEPT_CHANGES = [
    (
        "ClientError",
        {"copy_file", "copy_to", "move_to"},
        "a missing source raises exc.S3FileNotExist",
    ),
    (
        "ClientError",
        {"exists", "is_bucket_exists"},
        "a 403 raises exc.S3PermissionDenied (a PermissionError)",
    ),
    (
        "SystemError",
        {"sync", "sync_from", "sync_to"},
        "a failed sync raises exc.S3SyncError",
    ),
    (
        "KeyError",
        {"from_dict"},
        "a missing key raises exc.S3ValidationError (a ValueError)",
    ),
    (
        "ValueError",
        {"fname", "ext"},
        "fname / ext of a folder or void raise exc.S3PathIsNotFileError (a TypeError)",
    ),
    ("NotImplementedError", {"parse_tags"}, "a wrong type raises TypeError"),
]
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "site-packages",
    "__pycache__",
    "build",
    "dist",
    ".tox",
    ".mypy_cache",
    ".ipynb_checkpoints",
}


@dataclasses.dataclass(frozen=True)
class Finding:
    location: str
    line: int
    col: int
    rule_id: str
    category: str
    message: str


def _name_of(node: ast.AST) -> str | None:
    """
    The last name of ``a``, ``a.b`` or ``a.b.c``, else ``None``.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _dotted(node: ast.AST) -> str:
    """
    ``a.b.c`` for a chain of names, else ``""``.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted(node.value)
        if prefix == "":
            return ""
        return prefix + "." + node.attr
    return ""


def _str_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _keyword(call: ast.Call, name: str) -> ast.keyword | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


def _is_literal_file_path(call: ast.Call) -> bool:
    """
    ``S3Path("b", "folder")`` or ``S3Path("s3://b/folder")``: a call of
    ``S3Path`` whose arguments are all string literals and whose path is a
    file (no trailing ``/``). Anything not literal is unknown, so ``False``.
    """
    if _name_of(call.func) != "S3Path":
        return False
    if len(call.args) == 0 or len(call.keywords) > 0:
        return False
    values = list()
    for arg in call.args:
        value = _str_value(arg)
        if value is None:
            return False
        values.append(value)
    non_empty = list()
    for value in values:
        if value != "":
            non_empty.append(value)
    if len(non_empty) == 0:
        return False
    if non_empty[-1].endswith("/"):
        return False
    if len(non_empty) > 1:
        return True
    # one argument: a bucket alone is a folder; a key after it makes a file
    first = non_empty[0]
    if first.startswith("arn:"):
        return False
    if first.startswith("s3://"):
        first = first[len("s3://") :]
    return "/" in first


def _is_s3path_root(node: ast.BinOp) -> bool:
    """
    Whether a chain of ``/`` starts with an S3 path: an ``S3Path(...)`` call,
    or a variable whose name contains ``s3`` (``s3path``, ``s3dir``, ...).
    ``pathlib.Path`` joins the same way, so a chain on any other root is not
    reported; running the tests finds those.
    """
    root = node
    while isinstance(root, ast.BinOp) and isinstance(root.op, ast.Div):
        root = root.left
    if isinstance(root, ast.Call):
        return _name_of(root.func) == "S3Path"
    name = _name_of(root)
    if name is None:
        return False
    return "s3" in name.lower()


class _Scanner(ast.NodeVisitor):
    def __init__(self, location: str, line_offset: int = 0):
        self.location = location
        self.line_offset = line_offset
        self.findings: list[Finding] = list()
        self.parents: dict[ast.AST, ast.AST] = dict()

    def add(self, node: ast.AST, rule_id: str, detail: str = "") -> None:
        rule = RULES_BY_ID[rule_id]
        message = rule.title
        if detail != "":
            message = f"{message} ({detail})"
        self.findings.append(
            Finding(
                location=self.location,
                line=getattr(node, "lineno", 0) + self.line_offset,
                col=getattr(node, "col_offset", 0),
                rule_id=rule.id,
                category=rule.category,
                message=message,
            )
        )

    def scan(self, tree: ast.AST) -> list[Finding]:
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[child] = parent
        self.visit(tree)
        return self.findings

    # imports -------------------------------------------------------------
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            name = alias.name
            if module == "s3pathlib":
                if name == "context":
                    self.add(node, "M02", "-> from s3pathlib.api import s3_context")
                elif name == "compat":
                    self.add(node, "M12")
                elif name in TOP_LEVEL_NAMES:
                    self.add(node, "M01", f"-> from s3pathlib.api import {name}")
            elif module == "s3pathlib.api":
                if name == "context":
                    self.add(node, "M02", "-> from s3pathlib.api import s3_context")
                elif name in BETTER_CLIENT_NAMES:
                    self.add(node, "M13", f"-> better_client.{name}")
            elif module == "s3pathlib.aws":
                if name == "Context":
                    self.add(node, "M03")
                elif name == "context":
                    self.add(node, "M02", "-> from s3pathlib.api import s3_context")
            elif module.startswith("s3pathlib.compat"):
                self.add(node, "M12")
            elif module == "s3pathlib.utils" and name in HASH_NAMES:
                self.add(node, "M10", name)
            elif module == "s3pathlib.utils" and name in CONSOLE_URL_ATTRS:
                self.add(node, "M07", name)
            elif module == "s3pathlib.marker" and name in MARKER_NAMES:
                self.add(node, "M11", name)
            elif module == "s3pathlib.exc" and name in EXC_NAMES:
                self.add(node, "M14", name)
            elif module == "s3pathlib.validate" and name in VALIDATE_NAMES:
                self.add(node, "M18", name)
            elif module == "s3pathlib.tests.mock":
                self.add(node, "M16")
            elif module == "func_args" and name == "NOTHING":
                self.add(node, "M17")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.startswith("s3pathlib.compat"):
                self.add(node, "M12")
            elif alias.name == "s3pathlib.tests.mock":
                self.add(node, "M16")
        self.generic_visit(node)

    # attributes ----------------------------------------------------------
    def visit_Attribute(self, node: ast.Attribute) -> None:
        attr = node.attr
        owner = _name_of(node.value)
        dotted = _dotted(node)
        if attr in CONSOLE_URL_ATTRS:
            self.add(node, "M07", attr)
        elif attr == "delete_if_exists":
            self.add(node, "M08")
        elif attr in ("common_prefixs", "contents_and_common_prefixs"):
            self.add(node, "M09", attr)
        elif attr in HASH_NAMES:
            self.add(node, "M10", attr)
        elif attr == "DEFAULT_CHUNK_SIZE" and owner == "utils":
            self.add(node, "M10", attr)
        elif attr in MARKER_NAMES:
            self.add(node, "M11", attr)
        elif attr in EXC_NAMES:
            self.add(node, "M14", attr)
        elif attr in VALIDATE_NAMES and owner == "validate":
            self.add(node, "M18", attr)
        elif attr == "update_metadata":
            self.add(node, "M19")
        elif attr in ("attach_boto_session", "attach_sts_client"):
            self.add(node, "M02", attr)
        elif attr in CONTEXT_ATTRS and owner == "context":
            self.add(node, "M02", f"context.{attr}")
        elif dotted == "s3pathlib.context":
            self.add(node, "M02", "s3pathlib.context")
        elif attr in BETTER_CLIENT_NAMES and owner == "api":
            self.add(node, "M13", f"-> better_client.{attr}")
        elif attr == "bsm" and owner in ("cls", "self"):
            self.add(node, "S11", f"{owner}.bsm")
        self.generic_visit(node)

    # calls ---------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        method = _name_of(node.func)
        for name, rule_id, replacement in [
            ("bsm", "M04", "s3_client="),
            ("check_sum_algorithm", "M05", "checksum_algorithm="),
            ("quite", "M06", "quiet="),
            ("ignore_ext", "M15", 'compression="disable"'),
            ("is_us_gov_cloud", "M07", 'partition="aws-us-gov"'),
        ]:
            kw = _keyword(node, name)
            if kw is not None:
                self.add(kw, rule_id, f"-> {replacement}")

        if method == "open" and isinstance(node.func, ast.Attribute):
            for name in ("range", "part_number"):
                if _keyword(node, name) is not None:
                    self.add(node, "S06", f"{name}=")
            has_condition = False
            for name in ("if_match", "if_none_match"):
                if _keyword(node, name) is not None:
                    has_condition = True
            if has_condition:
                multipart = _keyword(node, "multipart_upload")
                is_false = False
                if multipart is not None:
                    if isinstance(multipart.value, ast.Constant):
                        if multipart.value.value is False:
                            is_false = True
                if is_false is False:
                    self.add(node, "S07")
        elif method == "filter_by_ext":
            for arg in node.args:
                value = _str_value(arg)
                if value is not None and value != "" and value.startswith(".") is False:
                    self.add(node, "S05", f"{value!r} -> {'.' + value!r}")
        elif method == "delete_object_versions":
            prefix = _keyword(node, "prefix")
            if prefix is not None:
                value = _str_value(prefix.value)
                if value is not None and value.endswith("/") is False:
                    self.add(
                        node,
                        "S09",
                        "-> delete_object_all_versions(key=...) for one key",
                    )
        elif method == "iterdir":
            self.add(node, "S02")
        elif method in ("sync", "sync_from", "sync_to"):
            if isinstance(node.func, ast.Attribute):
                self.add(node, "S10")
        elif method == "relative_to":
            for arg in node.args:
                if isinstance(arg, ast.Call) and _is_literal_file_path(arg):
                    self.add(node, "D02")
        elif method == "joinpath" and isinstance(node.func, ast.Attribute):
            target = node.func.value
            if isinstance(target, ast.Call) and _is_literal_file_path(target):
                self.add(node, "D01")

        if method == "delete":
            version_id = _keyword(node, "version_id")
            hard = _keyword(node, "is_hard_delete")
            if version_id is not None and hard is not None:
                if isinstance(hard.value, ast.Constant) and hard.value.value is True:
                    self.add(node, "S03")
        if method in ("copy_file", "delete") and isinstance(node.func, ast.Attribute):
            if self._result_is_used(node):
                self.add(node, "S01", f"{method}() result is used")
        self.generic_visit(node)

    def _result_is_used(self, node: ast.Call) -> bool:
        """
        ``False`` for a bare call, or ``_ = call()`` (the result is discarded).
        """
        parent = self.parents.get(node)
        if isinstance(parent, ast.Expr):
            return False
        if isinstance(parent, ast.Assign):
            discarded = True
            for target in parent.targets:
                if (isinstance(target, ast.Name) and target.id == "_") is False:
                    discarded = False
            if discarded:
                return False
        return True

    # assignments ---------------------------------------------------------
    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.ctx, ast.Store):
            if isinstance(node.value, ast.Attribute):
                if node.value.attr in ("metadata", "response"):
                    self.add(node, "S08", node.value.attr)
        self.generic_visit(node)

    # joins ---------------------------------------------------------------
    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Div):
            left = node.left
            if isinstance(left, ast.BinOp) and isinstance(left.op, ast.Div):
                middle = _str_value(left.right)
                if (
                    middle is not None
                    and middle != ""
                    and middle.endswith("/") is False
                    and _is_s3path_root(left)
                ):
                    self.add(node, "D01", f"{middle!r} -> {middle + '/'!r}")
            elif isinstance(left, ast.Call) and _is_literal_file_path(left):
                self.add(node, "D01")
        self.generic_visit(node)

    # try / except --------------------------------------------------------
    def visit_Try(self, node: ast.Try) -> None:
        names_in_body = set()
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Attribute):
                    names_in_body.add(sub.attr)
                elif isinstance(sub, ast.Name):
                    names_in_body.add(sub.id)
        for handler in node.handlers:
            caught = set()
            if handler.type is not None:
                types = [handler.type]
                if isinstance(handler.type, ast.Tuple):
                    types = list(handler.type.elts)
                for t in types:
                    name = _name_of(t)
                    if name is not None:
                        caught.add(name)
            for exc_name, methods, change in EXCEPT_CHANGES:
                if exc_name in caught and len(names_in_body & methods) > 0:
                    self.add(handler, "S04", f"except {exc_name}: {change}")
        self.generic_visit(node)


def scan_source(source: str, location: str, line_offset: int = 0) -> list[Finding]:
    """
    Scan Python source code.

    :raises SyntaxError: if it is not valid Python.
    """
    tree = ast.parse(source)
    return _Scanner(location, line_offset).scan(tree)


def _notebook_cells(path: Path) -> list[tuple[int, str]]:
    """
    The code cells of a notebook, as ``(cell number, source)``. IPython
    magics and shell lines are blanked, so the line numbers stay right.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    cells = list()
    number = 0
    for cell in data.get("cells", list()):
        number += 1
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        lines = list()
        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("%") or stripped.startswith("!"):
                lines.append("")
            else:
                lines.append(line)
        cells.append((number, "\n".join(lines)))
    return cells


def _iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = list()
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".py", ".ipynb"):
            continue
        parts = set(path.relative_to(root).parts[:-1])
        if len(parts & SKIP_DIRS) > 0:
            continue
        files.append(path)
    return files


def scan_path(root: Path) -> tuple[list[Finding], list[str]]:
    """
    Scan a file or every ``.py`` / ``.ipynb`` file under a folder.

    :return: the findings, and the errors (files that could not be parsed).
    """
    findings = list()
    errors = list()
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            errors.append(f"{path}: cannot read: {e}")
            continue
        if "s3pathlib" not in text and "S3Path" not in text:
            continue
        try:
            if path.suffix == ".ipynb":
                for number, source in _notebook_cells(path):
                    try:
                        findings.extend(scan_source(source, f"{path}[cell {number}]"))
                    except SyntaxError as e:
                        errors.append(f"{path}[cell {number}]: syntax error: {e}")
            else:
                findings.extend(scan_source(text, str(path)))
        except SyntaxError as e:
            errors.append(f"{path}: syntax error: {e}")
        except ValueError as e:
            errors.append(f"{path}: cannot parse: {e}")
    return findings, errors


def _main(path: Path | None, as_json: bool = False, list_rules: bool = False) -> int:
    """
    Scan ``path`` and print the findings (as text, or as JSON with
    ``as_json``), or print the rules with ``list_rules``.

    Returns 0 when the scan ran (with or without findings), 1 when ``path``
    does not exist.
    """
    if list_rules:
        for rule in RULES:
            print(f"{rule.id}  {rule.category:<10}  {rule.title}")
        return 0
    if path is None:
        print("ERROR: --path is required (or use --list_rules)", file=sys.stderr)
        return 1
    if path.exists() is False:
        print(f"ERROR: {path} does not exist", file=sys.stderr)
        return 1
    findings, errors = scan_path(path)
    findings = sorted(findings, key=lambda f: (f.location, f.line, f.col, f.rule_id))
    if as_json:
        output = {
            "findings": [dataclasses.asdict(f) for f in findings],
            "errors": errors,
        }
        print(json.dumps(output, indent=2))
    else:
        for f in findings:
            print(
                f"{f.location}:{f.line}:{f.col}: {f.rule_id} [{f.category}] {f.message}"
            )
        counts = dict()
        for f in findings:
            counts[f.category] = counts.get(f.category, 0) + 1
        summary = ", ".join(
            f"{counts.get(c, 0)} {c}" for c in (MECHANICAL, SEMANTIC, DEPRECATED)
        )
        print(f"{len(findings)} findings: {summary}")
        for error in errors:
            print(f"WARNING: {error}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scan",
        description="Find the code that needs a change to upgrade from s3pathlib 2.x to 3.x.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="a project folder, or one .py / .ipynb file",
    )
    parser.add_argument(
        "--as_json", action="store_true", help="print the findings as JSON"
    )
    parser.add_argument(
        "--list_rules", action="store_true", help="print the rules and exit"
    )
    args = parser.parse_args(argv)
    return _main(path=args.path, as_json=args.as_json, list_rules=args.list_rules)


if __name__ == "__main__":
    sys.exit(main())
