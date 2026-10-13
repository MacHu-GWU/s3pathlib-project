---
name: s3pathlib-upgrade-to-3
description: Upgrade a Python project from s3pathlib 2.x to 3.x. Scans the code and notebooks for 2.x usage, rewrites the mechanical changes such as imports, the bsm argument and the context object, flags the behavior changes for review, and finds deprecated path joins by running the tests.
argument-hint: "[project-dir]"
disable-model-invocation: true
---

# Upgrade s3pathlib 2.x to 3.x

Upgrade the project in `$ARGUMENTS` (the current directory if empty) from s3pathlib 2.x to 3.x. 3.0.0 is a breaking release: some changes are renames, some change behavior. Rewrite the renames; for every behavior change, read the code and decide with the user. Never change what the code does without saying so.

The rules, with the 2.x and 3.x code for each, are in [references/migration.md](references/migration.md). Read the section of a rule before you fix it.

## Steps

1. **Check the starting point.**
   - Find the s3pathlib version the project uses (`pyproject.toml`, `requirements*.txt`, the lock file, or `pip show s3pathlib`). If it is already 3.x, say so and stop.
   - 3.x needs Python 3.11 or newer. If the project supports older Pythons, ask the user before going on.
   - Check `git status`. If there are uncommitted changes, ask the user to commit or stash them first, so the upgrade is one reviewable diff. Do not commit yourself.

2. **Scan.** Run:

   ```bash
   python ${CLAUDE_SKILL_DIR}/scripts/scan.py --path <project-dir> --as_json
   ```

   Each finding has a location (`file.py:line`, or `notebook.ipynb[cell N]:line`), a rule id and a category: `mechanical`, `semantic` or `deprecated`. Static analysis does not know types: a `semantic` finding on a method name may be on an object that is not an `S3Path`; check before acting. `python scan.py --list_rules` prints all rules.

3. **Plan, then ask.** Show the user a short plan: the number of findings per category, the files touched, and every `semantic` finding with what you propose to do. Wait for the user to agree before editing.

4. **Update the dependencies.** Require `s3pathlib>=3.0.0,<4.0.0` and Python `>=3.11`. If the project imports `boto_session_manager`, `func_args` or `pathlib_mate` itself, add them to its own dependencies: s3pathlib no longer installs them.

5. **Fix the mechanical findings** (M rules) as `migration.md` says. Rerun the scan until no mechanical finding is left.

6. **Fix the deprecated findings** (D rules). Then run the project's tests with deprecation warnings as errors, which finds the joins onto a file that the scanner cannot see (paths built from variables):

   ```bash
   python -m pytest -W error::DeprecationWarning
   ```

   Fix each failure that comes from s3pathlib.

7. **Resolve the semantic findings** (S rules), one by one, as agreed in step 3. When the right fix depends on what the code means (which version to delete, whether the code relied on an order), ask the user.

8. **Review what the scanner cannot find.** Go through the last section of `migration.md` ("Not found by the scanner") and search the code for each item that may apply.

9. **Run the tests** (normally, then with `-W error::DeprecationWarning`) and report:
   - what was changed, per rule;
   - the semantic decisions and why;
   - anything left for the user, such as code without tests that you could not verify.

## Standing rules

- Use the public 3.x API only: `from s3pathlib.api import ...`, and `better_client` through `s3pathlib.api.better_client`.
- Keep a change minimal: fix the 2.x usage, do not refactor the code around it.
- In notebooks, edit the cell sources; do not edit outputs.
- If a finding is a false positive (not an s3pathlib object), leave the code alone and mention it in the report.
