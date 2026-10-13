# s3pathlib 2.x to 3.x migration reference

One section per rule of `scripts/scan.py` (same ids), then the changes the
scanner cannot find. Each section: what 2.x code looks like, what to write in
3.x, and what to check. The full list of changes, with the reasons, is the
`3.0.0` section of the s3pathlib release history.

Categories:

- **mechanical**: rewrite it, the meaning does not change.
- **semantic**: the behavior changed; read the surrounding code, then decide
  (and tell the user what you decided).
- **deprecated**: works in 3.x with a `DeprecationWarning`, raises in 4.0.0;
  fix it now.

## Mechanical

### M01 Top level import

```python
from s3pathlib import S3Path, ContentTypeEnum, and_, or_, not_   # 2.x
from s3pathlib.api import S3Path, ContentTypeEnum, and_, or_, not_   # 3.x
```

The same for `validate_s3_bucket`, `validate_s3_key`, `validate_s3_uri`,
`validate_s3_arn`. 3.x raises `ImportError` with this hint. Submodules still
import from the top level (`from s3pathlib import utils`, `exc`, ...), but
`import s3pathlib` alone no longer imports them: write `import s3pathlib.api`
or `from s3pathlib import utils` before using `s3pathlib.utils`.

### M02 context is now s3_context

| 2.x | 3.x |
|---|---|
| `from s3pathlib import context` | `from s3pathlib.api import s3_context` |
| `context.attach_boto_session(boto_ses)` | `s3_context.attach_s3_client(boto_ses.client("s3"))` |
| `context.s3_client` | `s3_context.s3_client` |
| `context.aws_account_id` | `boto_ses.client("sts").get_caller_identity()["Account"]` |
| `context.aws_region` | `s3_context.s3_client.meta.region_name` |
| `context.boto_ses`, `context.sts_client`, `attach_sts_client` | removed; keep your own session / clients |

`s3_context` creates the default client on first use, not at import.

### M03 Context class

`from s3pathlib.aws import Context` -> `from s3pathlib.aws import S3Context`.

### M04 bsm= is now s3_client=

Every method that calls AWS: `p.read_text(bsm=x)` -> `p.read_text(s3_client=...)`.
It accepts a boto3 S3 client only; anything else raises `TypeError`:

- `x` is a boto3 S3 client: `s3_client=x`.
- `x` is a `BotoSesManager`: `s3_client=x.s3_client`.
- `x` is a boto3 session: `s3_client=x.client("s3")`.

Check what the variable holds before rewriting. If the project used
`boto_session_manager` only for s3pathlib, it is no longer a dependency of
s3pathlib: keep it in the project's own dependencies if other code uses it.

### M05 check_sum_algorithm=

`delete(check_sum_algorithm=...)`, `put_bucket_versioning(check_sum_algorithm=...)`
and the `better_client` delete functions: rename to `checksum_algorithm=`.

### M06 quite=

`sync(..., quite=True)` (and `sync_from` / `sync_to`) -> `quiet=True`.

### M07 Console URLs and S3 Select

| 2.x | 3.x |
|---|---|
| `p.get_regional_console_url(region)` | `p.get_console_url(region=region)` |
| `p.us_gov_cloud_console_url` | `p.get_console_url(partition="aws-us-gov")` |
| `p.get_regional_us_gov_cloud_console_url(region)` | `p.get_console_url(region=region, partition="aws-us-gov")` |
| `utils.make_s3_console_url(..., is_us_gov_cloud=True)` | `utils.make_s3_console_url(..., partition="aws-us-gov")` |
| `p.s3_select_console_url` and the 3 other S3 Select URLs, `utils.make_s3_select_console_url` | removed (S3 Select is closed to new customers); build `https://console.aws.amazon.com/s3/buckets/{bucket}/object/select?prefix={key}` yourself if still needed |

`p.console_url` is unchanged.

### M08 delete_if_exists

`p.delete_if_exists()` -> `p.delete()`. Deleting what does not exist is not an
error. The return value changed from the number of deleted objects to an
`S3Path`: if the code used the count, use `count_objects()` before deleting.

### M09 common_prefixs

`paginate_list_objects_v2(...).common_prefixs()` -> `.common_prefixes()`, and
`.contents_and_common_prefixs()` -> `.contents_and_common_prefixes()`.

### M10 Hash helpers

`utils.md5_binary(b)` -> `hashlib.md5(b).hexdigest()`; `sha256_binary` ->
`hashlib.sha256(b).hexdigest()`; `hash_binary(b, hash_meth)` ->
`hash_meth(b).hexdigest()`; `hash_file(path, hashlib.md5)` -> open the file in
`"rb"` and `hashlib.file_digest(f, "md5").hexdigest()` (Python 3.11); with
`nbytes=n` it hashed the first `n` bytes only: `hashlib.md5(f.read(n)).hexdigest()`.
`DEFAULT_CHUNK_SIZE` is removed.

### M11 Deprecation helpers

`from s3pathlib.marker import deprecate_v1` (and `deprecate_v2`,
`warn_deprecate`, `warn_beta`) -> `from s3pathlib.marker import deprecated`, the
PEP 702 decorator: `@deprecated("Deprecated since X, will be removed in Y. Use Z instead.")`.

### M12 s3pathlib.compat

Removed (it only supported old `smart_open` versions). Delete the import.

### M13 better_client functions

2.x exposed them as `s3pathlib.api.<name>` (`import s3pathlib` then
`s3pathlib.api.is_bucket_exists(...)`). 3.x:

```python
from s3pathlib.api import better_client
better_client.is_bucket_exists(s3_client, bucket)
```

`better_client.delete_object_versions(prefix=...)` now needs a folder prefix,
see S09.

### M14 s3pathlib.exc

`exc._S3PathTypeError` -> `exc.S3PathTypeError`.
`exc.ensure_one_and_only_one_not_none` and `exc.ensure_all_none` are removed:
write the check yourself.

### M15 open(ignore_ext=...)

`p.open(..., ignore_ext=True)` -> `p.open(..., compression="disable")`.

### M16 Test base class

`from s3pathlib.tests.mock import BaseTest` -> `from s3pathlib.tests.mock_aws import BaseTest`.
See S11 for the attributes.

### M17 func_args.NOTHING

s3pathlib no longer uses `func_args`; an argument passed as `NOTHING` means
"not given": leave the argument out. `func-args` is no longer installed with
s3pathlib.

### M18 s3pathlib.validate

`S3BucketValidationError` / `S3KeyValidationError` -> `exc.S3ValidationError`
(a `ValueError`, so `except ValueError` keeps working). The charset constants
(`valid_bucket_charset`, `letter_and_number`, `safe_key_charset`, ...) are
removed: define the set yourself. 3.x accepts any UTF-8 key.

### M19 update_metadata

It always raised `NotImplementedError` in 2.x. To change the user metadata of
an object, copy it onto itself:
`p.copy_file(p, metadata={...}, overwrite=True)`.

## Semantic

### S01 copy_file and delete return a new S3Path

- `res = p.copy_file(dst)`: 2.x returned the boto3 response dict
  (`res["CopyObjectResult"]`); 3.x returns the `S3Path` of the copy, with
  `etag`, `last_modified_at`, `version_id`.
- `x = p.delete()`: 2.x returned `p` itself, with its cached metadata cleared;
  3.x returns a new `S3Path` and `p` does not change. With versioning, the
  returned path is the new delete marker (`is_delete_marker()` is `True`).
  Code that read `p.size` / `p.etag` after `delete()` expecting a fresh load
  needs `p.clear_cache()`.

### S02 iterdir order

2.x yielded the folders first, then the files. 3.x yields both mixed, in S3
key order. If the code relies on the grouping, sort:
`sorted(p.iterdir(), key=lambda x: x.is_file())`.

### S03 delete with version_id and is_hard_delete

2.x ignored `version_id` and deleted every version. 3.x raises `ValueError`:
`delete(version_id=v)` deletes one version, `delete(is_hard_delete=True)` all
versions of this exact key. Ask the user which one was meant.

### S04 Exception types

| 2.x catch | around | 3.x catch |
|---|---|---|
| `except ClientError` (`NoSuchKey`) | `copy_file`, `copy_to`, `move_to` | `except exc.S3FileNotExist` (a `FileNotFoundError`); other copy errors are still `ClientError` |
| `except ClientError` (403) | `S3Path(bucket).exists()`, `is_bucket_exists` | `except exc.S3PermissionDenied` (a `PermissionError`) |
| `except SystemError` | `sync`, `sync_from`, `sync_to` | `except exc.S3SyncError` (has `returncode`, `stderr`, `command`) |
| `except KeyError` | `S3Path.from_dict` | `except exc.S3ValidationError` (a `ValueError`) |
| `except ValueError` | `fname` / `ext` of a folder or void | `except exc.S3PathIsNotFileError` (a `TypeError`) |
| `except NotImplementedError` | `tag.parse_tags(non list)` | `TypeError` |

Every s3pathlib exception inherits `exc.S3PathlibError`. AWS errors of calls
with a response body (`NoSuchKey`, `NoSuchBucket`, `AccessDenied`, ...) are
still raised as boto3 raises them.

### S05 filter_by_ext needs a dot

`filter_by_ext("csv")` matched nothing in 2.x; 3.x raises `ValueError`. Write
`filter_by_ext(".csv")`. It is case insensitive, and skips folders.

### S06 open(range=...) / part_number

They never had an effect (smart_open sets its own range). To read part of an
object: `p.read_bytes(range="bytes=0-9")`, or `f.seek(offset)` then `f.read(n)`.

### S07 Conditional writes with open

2.x ignored `if_match` / `if_none_match` in `open("w")`. 3.x applies them only
with `multipart_upload=False` (one `put_object` on close) and raises
`ValueError` otherwise. Decide: add `multipart_upload=False`, or remove the
condition (it never worked).

### S08 metadata / response are copies

Changing `p.metadata[...]` or `p.response[...]` used to change the cache; now it
changes a copy. To change the user metadata in S3, copy the object onto itself
(M19).

### S09 delete_object_versions(prefix=...)

The prefix must end with `/` (a folder). To delete every version of one
object: `better_client.delete_object_all_versions(s3_client, bucket, key="data/file.txt")`.
2.x deleted every key starting with the string (`file.txt.bak` too).

### S10 sync identity

3.x runs `aws s3 sync` with the credentials and region of the S3 client
(`s3_client=...` or `s3_context`), not with `AWS_PROFILE` or the CLI default
profile. If the code relied on `AWS_PROFILE` for sync only, attach the client
of that profile: `s3_context.attach_s3_client(boto3.Session(profile_name=...).client("s3"))`.
Also: `include` / `exclude` take a list; all excludes come first, then all
includes; sync works on folders only.

### S11 Test base class attributes

`cls.bsm` is gone. Use `self.s3_client` (or `cls.s3_client`) for the client,
`cls.boto_ses` for the session, `cls.aws_account_id`, `cls.aws_region`.

## Deprecated

### D01 Joining onto a file

A path without a trailing `/` is a file; joining onto it is deprecated.

```python
S3Path("b") / "folder" / "file.txt"            # 2.x, deprecated in 3.x
S3Path("b") / "folder/" / "file.txt"           # 3.x
S3Path("b").joinpath("folder", "file.txt")     # 3.x
S3Path("b") / ["folder", "file.txt"]           # 3.x
S3Path("b", "folder").to_dir() / "file.txt"    # 3.x, for a path from a variable
```

The scanner only reports a chain that starts with `S3Path(...)` or with a
variable whose name contains `s3` (`s3path`, `s3dir`), because `pathlib.Path`
joins with `/` too; and `S3Path(...)` literals that are files. Run the tests
with `-W error::DeprecationWarning` to find the rest.

### D02 relative_to a file

`p.relative_to(S3Path("b", "folder"))` -> `p.relative_to(S3Path("b", "folder/"))`
(or `.to_dir()`). Also new: `S3Path("b", "a/").relative_to(S3Path("b", "a"))`
returned void in 2.x and raises `ValueError` in 3.x.

## Not found by the scanner

Look for these by reading the code, or let the tests find them (most raise):

- **Python and dependencies.** Python 3.11 or newer. `boto3>=1.41.0`,
  `smart-open>=7.0.0,<9.0.0`. `pathlib-mate`, `func-args`,
  `boto-session-manager` are no longer installed with s3pathlib.
- **Attributes on a path.** `p.my_attr = 1` raises `AttributeError`
  (`__slots__`). Keep the data in a `dict` keyed by the path.
- **change().** Invalid arguments raise `ValueError` instead of giving an odd
  path: `new_ext` must start with `.`; `new_fname` / `new_ext` cannot contain
  `/`; `new_basename` cannot be empty; a top level file cannot use
  `new_dirname` (use `new_dirpath`).
- **Listing a file.** `S3Path("b", "file.txt").iter_objects()` / `.iterdir()`
  listed every key with that string prefix; 3.x raises `S3PathIsNotFolderError`.
  To list by a string prefix:
  `better_client.paginate_list_objects_v2(s3_client, bucket, prefix=...)`.
- **Keys with // or a leading /.** Listing them raises `S3ValidationError`
  (the path would be another key); list them with `better_client`.
- **Metadata snapshot.** `exists()` and `read_bytes()` only fill an empty
  snapshot and no longer refresh it: call `p.head_object()` or
  `p.clear_cache()` for the latest metadata. A listed old version loads its
  missing metadata from its own version. The `metadata` of a delete marker is
  `None` (it raised `S3FileNotExist`).
- **Sort order.** `sorted(paths)` puts a folder right before its content (like
  `pathlib`); for the S3 key string order, `sorted(paths, key=lambda p: p.key)`.
- **copy_dir / move_to.** Copy every key, folder markers included (and count
  them); overlapping source and target folders raise `ValueError`;
  `copy_source_if_*` on a folder, and `version_id` on a folder copy, raise
  `ValueError`.
- **version_id on a folder or bucket.** `exists(version_id=...)`,
  `ensure_not_exists(version_id=...)` raise `ValueError`.
- **open().** A key containing `?versionId=` raises `ValueError` (use
  `read_bytes` / `write_bytes`); `open("w", version_id=...)` raises.
- **Invalid URIs.** `S3Path("https://...")` and `split_s3_uri("https://...")`
  raise `S3ValidationError`.
- **validate_s3_bucket.** Only checks the rules for a new general purpose
  bucket: access point aliases and directory bucket names are rejected.
- **bucket delete_bucket().** No longer clears the snapshot of the path.
