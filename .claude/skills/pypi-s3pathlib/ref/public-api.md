# s3pathlib 3.0.0 — public API reference

Import only through `s3pathlib.api`: `from s3pathlib.api import S3Path` or `import s3pathlib.api as s3pathlib`.

## Conventions that apply everywhere

- **boto3 pass-through kwargs.** Methods that wrap a boto3 call also accept that call's parameters in snake_case (`content_type`, `cache_control`, `if_match`, `version_id`, `expected_bucket_owner`, `expires_datetime` = `Expires`, ...). Omitted means "not sent"; passing `None` is sent and rejected by botocore. Signatures below show them as `**boto3_kwargs`.
- **`s3_client: S3Client | None = None`** on every AWS method. `None` uses `s3_context.s3_client`. Pass a client, not a `boto3.Session`.
- **Errors from AWS calls are raised as is** (`botocore.exceptions.ClientError` with `NoSuchKey`, `NoSuchBucket`, `AccessDenied`, ...). Only HEAD calls (`exists`, `head_object`, property loading) are converted to `exc.S3FileNotExist` / `exc.S3PermissionDenied`.
- **Writes return a new `S3Path`** carrying a metadata snapshot of what was written; the path you called it on is never mutated.
- **`overwrite=False` by default** for `copy_*`, `move_to`, `upload_*`: raises `exc.S3FileAlreadyExist`.

## `S3Path`

### Path kinds

Six kinds; the last non-empty part decides file vs dir (trailing `/` = dir).

| kind | example | `is_file` | `is_dir` | `is_bucket` | `is_relpath` | `is_void` |
|---|---|---|---|---|---|---|
| file | `S3Path("b", "a", "f.txt")` | T | | | | |
| dir | `S3Path("b", "a/")` | | T | | | |
| bucket (root dir) | `S3Path("b")` | | T | T | | |
| relative file | `S3Path.make_relpath("a", "f.txt")` | T | | | T | |
| relative dir | `S3Path.make_relpath("a/")` | | T | | T | |
| void | `S3Path()` | | | | T | T |

### Construction (no AWS call)

```
S3Path(*args: str | S3Path)            # first arg: bucket, "bucket/key", "s3://...", or "arn:...:s3:::..."; rest: key parts
S3Path.from_s3_uri(uri: str) -> S3Path  # strict: only s3:// URIs (S3ValidationError otherwise)
S3Path.from_s3_arn(arn: str) -> S3Path  # any partition
S3Path.from_bucket(bucket: str) -> S3Path
S3Path.make_relpath(*parts: str | S3Path) -> S3Path
S3Path.from_dict(dct: S3PathDict) -> S3Path / p.to_dict() -> S3PathDict
```
`/` and `""` parts are collapsed; only format is checked, not bucket naming rules (use `validate_s3_bucket`). An `https://` URL raises `S3ValidationError`.

### Attributes (no AWS call)

`bucket`, `key` (dir key ends with `/`; bucket/void → `""`), `uri` (`None` without bucket), `parts`, `basename` (pathlib `name`), `fname` (`stem`, file only), `ext` (`suffix`, file only — raises `S3PathIsNotFileError` on a dir), `dirname`, `abspath` (`"/" + key`), `dirpath`, `parent` (always a dir), `parents`, `root` (bucket root), `arn`, `console_url`.
`get_arn(partition="aws") -> str | None`; `get_console_url(region=None, partition="aws") -> str | None`.

### Join / change / relative (no AWS call)

```
p / "part" / ["a", "b.txt"]; p.joinpath(*other: str | S3Path) -> S3Path
p.change(new_bucket=, new_abspath=, new_dirpath=, new_dirname=, new_basename=, new_fname=, new_ext=) -> S3Path
p.to_dir() / p.to_file() -> S3Path
p.relative_to(other) -> S3Path        # also `p - other`; inverse of `/`; ValueError if not under other
p.copy() -> S3Path                     # equal path, no snapshot
p.is_parent_of(other) / p.is_prefix_of(other) -> bool
```
Joining onto a **file** (`S3Path("b") / "folder" / "x"`) is deprecated (DeprecationWarning; error in 4.0). Join onto a dir: `"folder/"`, or pass all parts at once. `change` raises `ValueError` on conflicting args or `new_ext` without leading dot.

Comparison: equality/hash use bucket + parts + file/dir only (never metadata or version). Sorting is part by part like pathlib (a dir right before its content), **not** S3's key-string order; use `key=lambda p: p.key` for that.

### Type checks

`is_file()`, `is_dir()`, `is_bucket()`, `is_relpath()`, `is_void()`, `is_delete_marker()`.
`ensure_file()` / `ensure_object()`, `ensure_not_file()` / `ensure_not_object()`, `ensure_dir()`, `ensure_not_dir()`, `ensure_bucket()`, `ensure_relpath()`, `ensure_not_relpath()` → `None` or raise an `exc.S3PathTypeError` subclass.

### Exists / metadata snapshot

```
exists(version_id=..., s3_client=None) -> bool        # bucket: head_bucket; file: head_object (delete marker = False); dir: any key with the prefix
ensure_not_exists(version_id=..., s3_client=None) -> None
head_object(version_id=..., s3_client=None) -> dict   # reload latest, replace snapshot in place; S3FileNotExist if missing
clear_cache() -> None
```
Metadata properties: `size`, `size_for_human`, `etag` (no quotes), `last_modified_at`, `version_id` (`"null"` if written without versioning), `expire_at`, `metadata` (user `x-amz-meta-*`, keys lower-cased, a copy), `response` (raw snapshot dict).

Snapshot rules: a path holds metadata of **one version at one moment**. Full snapshot from `head_object`/`exists`/`read_*`; partial from list/write calls. Reading a missing field of a partial snapshot calls `head_object` of the same version (`VersionId`, or `IfMatch=etag`) and raises `exc.S3ObjectChangedError` if the object changed. A path with no snapshot loads the latest on first property read. Snapshots never auto-refresh; methods never use the snapshot's version — pass `version_id=p.version_id` explicitly.

### Read / write

```
read_bytes(version_id=..., s3_client=None, **boto3_kwargs) -> bytes          # get_object
read_text(encoding="utf-8", errors="strict", ..., s3_client=None) -> str
write_bytes(data: bytes, metadata=..., tags=..., s3_client=None, **boto3_kwargs) -> S3Path   # put_object
write_text(data: str, encoding="utf-8", errors="strict", metadata=..., tags=..., ...) -> S3Path
touch(exist_ok=False, metadata=..., tags=..., s3_client=None, **boto3_kwargs) -> None       # atomic IfNoneMatch="*"
mkdir(exist_ok=False, parents=False, s3_client=None) -> None   # folder marker "dir/"; parents=True writes every parent marker
open(mode="r", version_id=..., encoding=None, errors=None, newline=None, compression=None,
     multipart_upload=True, metadata=..., tags=..., transport_params=None, s3_client=None, **boto3_kwargs) -> IO
```
- `metadata` / `tags`: `dict[str, str]`. Conditional writes: `if_none_match="*"` (only if absent), `if_match=etag`; failure raises `ClientError` `PreconditionFailed`.
- `open` uses smart_open (streaming). Compression inferred from extension (`.gz`, `.bz2`, `.zst`); `compression="disable"` for raw bytes. Write only commits on close; an exception inside `with` aborts. `if_match`/`if_none_match`/`content_md5`/checksums need `multipart_upload=False`. Keys containing `?versionId=` raise `ValueError`.
- `mkdir` on a bucket raises; folder "exists" in S3 without marker too.

### Upload / sync

```
upload_file(path: PathType, overwrite=False, extra_args=..., callback=..., config=..., s3_client=None) -> S3Path  # boto3 upload_file, multipart
upload_dir(local_dir: PathType, pattern="**/*", overwrite=False, s3_client=None) -> int   # p must be a dir; returns count
S3Path.sync(src, dst, s3_client=None, include=None, exclude=None, acl=None, only_show_errors=False,
            no_progress=False, page_size=None, delete=False, verbose=True, quiet=True) -> None
p.sync_from(src, ...) / p.sync_to(dst, ...)
```
`sync` shells out to `aws s3 sync` (needs the `aws` CLI, else `FileNotFoundError`) with the client's credentials. `src`/`dst`: S3Path dir, `s3://` URI, or local path; at least one in S3. All `exclude` are applied before all `include`. Failure raises `exc.S3SyncError` (exit code + stderr). `quite=` is a deprecated alias of `quiet`. `upload_file`'s overwrite check is not atomic.

### List / count

```
iter_objects(batch_size=1000, limit=None, recursive=True, s3_client=None, **boto3_kwargs) -> S3PathIterProxy
iterdir(batch_size=1000, limit=None, s3_client=None, **boto3_kwargs) -> S3PathIterProxy      # one level, files + sub dirs
list_object_versions(batch_size=1000, limit=None, delimiter=..., s3_client=None, ...) -> S3PathIterProxy
count_objects(include_folder=False, s3_client=None) -> int
calculate_total_size(for_human=False, include_folder=False, s3_client=None) -> tuple[int, int | str]
```
- Path must be a dir (or bucket) for `iter_objects`/`iterdir`/count; `S3PathIsNotFolderError` otherwise. Folder markers are skipped.
- Yielded paths carry a partial snapshot (`size`, `etag`, `last_modified_at`; versions also `version_id`, `is_delete_marker()`).
- Order is S3 key-string order. `list_object_versions` on a file lists only that exact key; per key newest first.
- `limit=0` returns nothing without calling AWS.

### Copy / move / delete

```
copy_file(dst, version_id=..., metadata=..., tags=..., overwrite=False, s3_client=None, **boto3_kwargs) -> S3Path  # copy_object
copy_dir(dst, metadata=..., tags=..., overwrite=False, s3_client=None, **boto3_kwargs) -> int
copy_to(dst, ...) -> int        # dispatches to copy_file / copy_dir; returns count
move_to(dst, ...) -> int        # copy_to then delete exactly the copied source keys; not atomic
delete(version_id=..., is_hard_delete=False, skip_prompt=False, s3_client=None, **boto3_kwargs) -> S3Path
```
- Copy keeps source metadata, tags and headers; passing one replaces only that one. Copy to itself with new metadata edits it in place. Objects > 5 GB are not supported (use boto3 `s3_client.copy`).
- `copy_dir` / `move_to` reject overlapping folders (`ValueError`); `copy_dir(overwrite=False)` checks all targets first and copies nothing on conflict.
- `delete`: file → delete (delete marker with versioning); `version_id` → that version permanently; `is_hard_delete=True` → all versions + markers of this exact key / under the folder; dir → every object under it; bucket path → empties the bucket after a `YES` prompt (`skip_prompt=True` in scripts). Missing targets are not an error. Partial failure raises `exc.S3DeleteObjectsError`.

### Tags

```
get_tags(version_id=..., s3_client=None, ...) -> tuple[str | None, dict[str, str]]     # (version_id, tags)
put_tags(tags, version_id=..., s3_client=None, ...) -> tuple[str | None, dict]          # replace all
update_tags(tags, version_id=..., s3_client=None, ...) -> tuple[str | None, dict]       # dict.update; read-merge-write, not atomic
```

### Buckets / versioning

```
S3Path.list_buckets(s3_client=None) -> list[S3Path]       # all pages
create_bucket(region=None, s3_client=None, **boto3_kwargs) -> dict    # S3PathIsNotBucketError if not a bucket path
delete_bucket(expected_bucket_owner=..., s3_client=None) -> dict      # must be empty (incl. versions / markers); BucketNotEmpty
get_bucket_versioning(s3_client=None) -> dict
put_bucket_versioning(enable_versioning: bool, enable_mfa_delete=None, s3_client=None, ...) -> dict
is_versioning_enabled(s3_client=None) -> bool / is_versioning_suspended(s3_client=None) -> bool
```

## `S3PathIterProxy`

Iterable once. `all() -> list`, `one()`, `one_or_none()`, `many(k)`, `skip(k)`, `iter_chunks(k)`, `filter(*funcs)` (AND), `filter_by_ext(*exts)` (case-insensitive, `""` = no extension).
Filter functions come from comparing class-level properties: `S3Path.size >= 1000`, `S3Path.ext == ".csv"`, `S3Path.key.startswith(...)`, `.endswith`, `.contains`, `.between(lo, hi)`. Filterable: `bucket key uri arn parts basename fname ext dirname abspath dirpath size etag last_modified_at version_id expire_at`. Filters run client-side after listing.

## `and_(*funcs)`, `or_(*funcs)`, `not_(func)`

Combine filter callables (from `iterproxy`). E.g. `.filter(or_(S3Path.ext == ".csv", S3Path.ext == ".tsv"))`.

## `s3_context`

`s3_context.attach_s3_client(s3_client)` sets the default client; `s3_context.s3_client` returns it, lazily creating `boto3` default-credential client on first use. A path returned by a call with explicit `s3_client=` remembers it **only** to load its own metadata; other calls on it still use their own `s3_client` arg or the default.

## `exc`

All inherit `S3PathlibError` plus a builtin, so builtin `except` works.

| exception | builtin base | raised when |
|---|---|---|
| `S3PathTypeError` → `S3PathIsNotFileError`, `S3PathIsNotFolderError`, `S3PathIsNotBucketError`, `S3PathIsNotRelpathError` | `TypeError` | wrong kind of path |
| `S3ValidationError` | `ValueError` | invalid URI / ARN / bucket / key / dict |
| `S3NotExist` → `S3FileNotExist`, `S3FolderNotExist`, `S3BucketNotExist` | `FileNotFoundError` | HEAD 404 |
| `S3AlreadyExist` → `S3FileAlreadyExist`, `S3FolderAlreadyExist`, `S3BucketAlreadyExist` | `FileExistsError` | `overwrite=False` / `exist_ok=False` |
| `S3PermissionDenied` | `PermissionError` | HEAD 403 |
| `S3ObjectChangedError` | — | partial snapshot's object changed |
| `S3DeleteObjectsError` | — | `delete_objects` reported per-key errors |
| `S3SyncError` | — | `aws s3 sync` failed |

Wrong Python type → builtin `TypeError`; conflicting / invalid value → builtin `ValueError`.

## `utils`

```
split_s3_uri(s3_uri) -> (bucket, key);  join_s3_uri(bucket, key) -> str
split_s3_arn(s3_arn) -> (AwsPartitionEnum, bucket, key)
split_parts(key) -> list[str];  smart_join_s3_key(parts, is_dir) -> str
ensure_s3_object(key_or_uri) / ensure_s3_dir(key_or_uri) -> None
repr_data_size(size_in_bytes, precision=2) -> str   # 1024-based, "1.50 KB"
parse_data_size(s) -> int                           # inverse
make_s3_console_url(bucket=None, prefix=None, s3_uri=None, version_id=None, aws_region=None, partition="aws") -> str
grouper_list(iterable, n) -> Iterable[list]
```

## `better_client`

Functions on a raw boto3 client; first args `(s3_client, bucket, key_or_prefix, ...)`, rest are boto3 snake_case kwargs. `prefix` is a string prefix (`"folder"` also matches `"folder-2/"`).

```
head_object(s3_client, bucket, key, ...) -> dict | None   # None if missing
is_object_exists(s3_client, bucket, key, version_id=...) -> bool
is_bucket_exists(s3_client, bucket) -> bool
paginate_list_objects_v2(s3_client, bucket, prefix, batch_size=1000, limit=None, delimiter=..., ...) -> ListObjectsV2OutputTypeDefIterproxy
   # .contents() / .common_prefixes() / .contents_and_common_prefixes()
paginate_list_object_versions(s3_client, bucket, prefix, batch_size=1000, limit=None, ...) -> ListObjectVersionsOutputTypeDefIterproxy
   # .versions() / .delete_markers() / .common_prefixes() / .versions_and_delete_markers_and_common_prefixes()
is_content_an_object(content) -> bool        # False for a folder marker
count_objects(s3_client, bucket, prefix, include_folder=False) -> int
calculate_total_size(s3_client, bucket, prefix, include_folder=False) -> (count, bytes)
delete_object(s3_client, bucket, key, version_id=..., ...) -> dict
delete_dir(s3_client, bucket, prefix, batch_size=1000, limit=None, ...) -> int
delete_object_versions(s3_client, bucket, prefix, ...) / delete_object_all_versions(s3_client, bucket, key, ...) -> int
update_object_tagging(s3_client, bucket, key, tags, version_id=...) -> (version_id, tags)
update_bucket_tagging(s3_client, bucket, tags) -> tags
upload_dir(s3_client, bucket, prefix, local_dir, pattern="**/*", overwrite=False) -> int
```
Iterproxy classes: `ObjectTypeDefIterproxy`, `CommonPrefixTypeDefIterproxy`, `ObjectVersionTypeDefIterproxy`, `DeleteMarkerEntryTypeDefIterproxy`, `ListObjectsV2OutputTypeDefIterproxy`, `ListObjectVersionsOutputTypeDefIterproxy`. See `s3pathlib/better_client/` for exact signatures.

## Small symbols

- `ContentTypeEnum` — plain class of str constants: `image_jpeg`, `image_png`, `image_gif`, `image_bmp`, `image_tiff`, `image_svg_xml`, `html`, `text_plain`, `text_rtf`, `app_pdf`, `app_json`, `app_zip`, `app_gzip`, `app_ms_word`, `audio_mpeg`, ...
- `AwsPartitionEnum` — `aws`, `aws_cn`, `aws_us_gov`, `aws_eusc` (values `"aws"`, `"aws-cn"`, ...).
- `S3PathDict` — `TypedDict{bucket: str | None, parts: list[str], is_dir: bool | None}`.
- `validate_s3_bucket(bucket)`, `validate_s3_key(key)`, `validate_s3_uri(uri)`, `validate_s3_arn(arn)` → `None` or `exc.S3ValidationError`.

## Key scenarios

### 1. Write, read, list, filter

```python
import boto3
from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.api import exc

s3_context.attach_s3_client(boto3.Session(profile_name="my-profile").client("s3"))

s3dir = S3Path("my-bucket", "data/")            # trailing "/" = folder
p = s3dir / "2024/" / "report.csv"              # "2024" without "/" is a file: joining onto it is deprecated

p_new = p.write_text("a,b\n1,2\n", metadata={"owner": "alice"}, content_type="text/csv")
print(p_new.size, p_new.etag)                   # from the write snapshot, no extra call
print(p.read_text())

for f in s3dir.iter_objects().filter(S3Path.ext == ".csv", S3Path.size > 0):
    print(f.uri, f.size)                         # size from the list call
```

### 2. Copy, move, delete safely

```python
src = S3Path("s3://my-bucket/data/2024/")
try:
    src.copy_dir(S3Path("s3://my-bucket/backup/2024/"))           # overwrite=False by default
except exc.S3FileAlreadyExist:
    src.copy_dir(S3Path("s3://my-bucket/backup/2024/"), overwrite=True)
S3Path("s3://my-bucket/tmp/").move_to(S3Path("s3://my-bucket/archive/tmp/"))
S3Path("s3://my-bucket/archive/").delete()                         # every object under it
S3Path("my-bucket", "f.txt").write_bytes(b"x", if_none_match="*") # create only if absent
```

### 3. Versions

```python
p = S3Path("versioned-bucket", "f.txt")
p.write_text("v1"); p.write_text("v2")
versions = p.list_object_versions().all()        # newest first
oldest = versions[-1]
print(p.read_text(version_id=oldest.version_id)) # "v1"; without version_id you get the latest
p.copy_file(p, version_id=oldest.version_id, overwrite=True)  # restore v1 as latest
p.delete()                                        # adds a delete marker
p.delete(is_hard_delete=True)                     # remove every version and marker
```
