---
name: write-pypi-skill
description: A meta skill that reads the Python library at the current working directory and generates a reusable Agent Skill for it, named after the package, that documents the library's public API and, if present, its command line interface. The user invokes this when they want to turn a local Python library into a Claude skill so future sessions can use the library through its public surface without re-reading the source.
disable-model-invocation: true
---

# Write a pypi-package skill

Generate an Agent Skill that lets future Claude sessions use the local Python library through its public API, without re-loading the source.

## Naming convention

The generated skill must be **prefixed with `pypi-`** so it's clearly namespaced as a pypi-package skill and won't collide with other skills that happen to share the same word. The separator between the `pypi` prefix and the package name is a **hyphen**, while underscores inside the package name itself are preserved verbatim (Python package convention). A package named `<package_name>` becomes the skill `pypi-<package_name>`, invoked as `/pypi-<package_name>`.

## Where to write the output

Always write to **`.claude/skills/pypi-<package_name>/` inside the current project**. Overwrite any existing directory at that path without prompting — the skill is meant to stay in sync with the project's current public API, so regenerating is the expected way to refresh it.

## Step 1 — Inspect the project

Read `pyproject.toml` at the working-directory root and extract:

- `[project].name` → take it verbatim (underscores stay underscores) and prepend `pypi-` (hyphen separator) to form the skill command (e.g. `<package_name>` → `/pypi-<package_name>`).
- `[project].version` → record for the skill header.
- `[project.scripts]` → if present, the library exposes a CLI. Note the entry point, e.g. `mycli = "package.cli:main"`. Remember the CLI executable name (the key on the left).

## Step 2 — Walk the public API

The library's stable public surface lives at `<package_name>/api.py`. Read it top to bottom; **one `from ... import X` per line == one public symbol**.

For each symbol, find where it actually lives, then:

- **Constant / function** — open its source. Record signature, docstring, and what it returns.
- **Class / dataclass** — also list its non-underscore methods and properties. For each: signature + one-line docstring summary. For dataclasses, list the fields too.
- **Sub-api module** (e.g. `import <package>.<sub>.api as <sub>`) — recurse into that subpackage's `api.py` and apply the same rules. Sub-api symbols are referenced as `<sub>.<symbol>` by the user.

Skip anything starting with `_` — that's internal and explicitly out of scope.

Users always import through `api.py`, never reach into internal modules. Document only these two canonical forms:

```python
from <package>.api import X
import <package>.api as <package>     # then <package>.X
```

## Step 3 — Read `tests/` for understanding

Grep `tests/` for each public symbol to understand how the API is actually used. This is **input for your own understanding** — do **not** copy tests wholesale into the generated docs. Most of what you read here stays in your head; only 1–3 representative usage patterns make it into `ref/public-api.md` as the "Key scenarios" section (see Step 5).

## Step 4 — Inspect the CLI (only when `[project.scripts]` exists)

Resolve the entry-point module from `[project.scripts]` and read it. Walk the command tree fully: every subcommand, every flag, every default. You'll need all of this for `ref/cli.md`.

## Step 5 — Write the skill

Create this layout:

```
.claude/skills/pypi-<package_name>/
├── SKILL.md
└── ref/
    ├── public-api.md
    └── cli.md          # only if the library has a CLI
```

### SKILL.md — index, not reference (always-loaded)

This file stays in context the whole session whenever the skill triggers, so it must scale to 30+ public symbols without bloat. Think of it as an **index**: it tells the agent *what exists* and *what it's for*, nothing more. Signatures, semantics, examples all live in `ref/public-api.md`.

Required sections:

- **Frontmatter `name`** — `pypi-<package_name>`.
- **Frontmatter `description`** — write as one descriptive paragraph in plain prose. **Lead with what the library does** (functionality first), then name the top public symbols so the router has concrete words to match on. **Keep the text YAML-safe** — no colons, no quotation marks (single or double), no backticks, no brackets; just plain sentences with periods and commas. **End with a single-sentence version-compatibility note** in this style (substitute the package name and the version captured in Step 1): *Generated for `<package_name>` version `<version>`. Higher installed versions should generally be compatible, lower versions may still work but correctness is not guaranteed.* The generated skill is meant to auto-trigger whenever the agent works with this library, so do not set `disable-model-invocation`.
- **One-paragraph purpose** — what the library is for.
- **Import** — the two canonical forms (`from <package>.api import X` / `import <package>.api as <package>`). Nothing else.
- **Public API** — flat list, **one line per symbol**, format: `` `<symbol_name>` — one short sentence on what it does. `` No signatures, no fields, no method enumerations. For a class, the class itself is one line; its methods do not appear here.
- **CLI** *(only when applicable)* — one short paragraph: command is typically `.venv/bin/<cli-name>`; run `<cli-name> -h` for help; full args live in `ref/cli.md`. **Do not enumerate subcommands here.**
- **More detail** — pointers: "For signatures and key examples see `ref/public-api.md`. For full CLI args see `ref/cli.md`."

### `ref/public-api.md` — API reference (lazy-loaded)

Audience: an engineer **using** the library, not maintaining it. This file is lazy-loaded but still needs to scale to 30+ symbols — keep each entry tight.

For each public symbol:

- Full typed signature (one or a few lines). For classes, list the public methods with their signatures too — one line each.
- 2–3 lines on parameter / return semantics. State the *what*; state the *why* only when non-obvious (invariants, gotchas, design constraints the user must respect).
- **No per-symbol usage example.** If a specific call is non-obvious, point to the source (e.g. "see `<package>/<module>.py`") rather than copying code.

After the per-symbol list, add a **Key scenarios** section: **1–3** short, end-to-end snippets that show the most representative usage patterns of the library as a whole (distilled from `tests/`, trimmed to the essentials — not copied verbatim). This is the only place real code samples live in the generated skill, and they cover the *library*, not individual symbols.

### `ref/cli.md` — full CLI reference (lazy-loaded)

Audience needs to use the CLI **without** running `--help`. This file loads when the user mentions the CLI, so it must be complete:

- For each subcommand: short description, every flag with type and default, one short example.
- A small table per subcommand reads well.

Stay terse — complete ≠ verbose.

## Conciseness discipline

Every line in `SKILL.md` stays in the conversation once invoked — it is a recurring token cost. Prefer signatures, tables, and short examples over prose. The same discipline applies (less strictly) to `ref/*` since they are lazy-loaded.

## Verify before finishing

Sanity-check that documented symbols actually exist. For 2–3 representative symbols, run:

```bash
uv run python -c "from <package>.api import <symbol>"
```

If any import fails, the public API docs are wrong — fix them before reporting done.
