---
name: pypi-s3pathlib
description: Python library s3pathlib, a pathlib-like object oriented layer over boto3 S3. Build and manipulate S3 paths without AWS calls, read and write objects, open them as streamed file objects, list and filter folders, read metadata and tags, copy, move and delete files and folders, work with object versions and buckets, upload local files and run aws s3 sync. Public symbols include S3Path, S3PathIterProxy, s3_context, exc, utils, better_client, ContentTypeEnum, AwsPartitionEnum, S3PathDict, validate_s3_bucket, validate_s3_key, validate_s3_uri, validate_s3_arn, and_, or_, not_. Generated for s3pathlib version 3.0.0. Higher installed versions should generally be compatible, lower versions may still work but correctness is not guaranteed.
---

# s3pathlib

`S3Path` is to an S3 bucket + key what `pathlib.Path` is to a drive + path: an immutable path object whose pure methods never call AWS, plus methods that call S3 through boto3 (default client from `s3_context`, or `s3_client=` per call). For upgrading 2.x code, use the `s3pathlib-upgrade-to-3` skill.

## Import

```python
from s3pathlib.api import S3Path
import s3pathlib.api as s3pathlib     # then s3pathlib.S3Path
```

## Public API

- `S3Path` — the path class: build / join / change paths, and every S3 operation (read, write, list, copy, delete, metadata, tags, versions, buckets, upload, sync).
- `S3PathIterProxy` — one-shot iterator of `S3Path` returned by the list methods, with `.all()`, `.one()`, `.filter(...)`, `.filter_by_ext(...)`.
- `s3_context` — global holder of the default boto3 S3 client (`attach_s3_client`).
- `exc` — s3pathlib exceptions (`S3FileNotExist`, `S3FileAlreadyExist`, `S3PathIsNotFolderError`, ...).
- `utils` — string helpers: split / join S3 URIs and ARNs, data-size formatting and parsing, console URL.
- `better_client` — lower-level functions on a raw boto3 client (paginators, head / delete / tagging helpers, `upload_dir`).
- `ContentTypeEnum` — common MIME types as string constants for `content_type=`.
- `AwsPartitionEnum` — AWS partitions (`aws`, `aws-cn`, `aws-us-gov`, `aws-eusc`) for ARNs and console URLs.
- `S3PathDict` — TypedDict of `S3Path.to_dict()` / `from_dict()`.
- `validate_s3_bucket` — raise `S3ValidationError` if a name breaks the new-bucket naming rules.
- `validate_s3_key` — raise if a key is not UTF-8 or over 1024 bytes.
- `validate_s3_uri` — raise if a string is not a valid `s3://bucket/key` URI.
- `validate_s3_arn` — raise if a string is not a valid S3 bucket / object ARN.
- `and_` / `or_` / `not_` — combine filter functions for `S3PathIterProxy.filter`.

## More detail

For signatures, semantics, gotchas and key examples see `ref/public-api.md`. The library has no CLI.
