.. _release_history:

Release and Version History
==============================================================================

:orphan:


Backlog (TODO)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- make :class:`s3pathlib.aws.Context` multi-thread safe.

**Minor Improvements**

**Bugfixes**

**Miscellaneous**


3.0.0 (2026-10-05)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Breaking Changes**

- Remove the top level names of ``from s3pathlib import ...`` (``S3Path``, ``s3_context``, ``ContentTypeEnum``, ``validate_s3_bucket`` / ``key`` / ``uri`` / ``arn``, ``and_``, ``or_``, ``not_``); import them with ``from s3pathlib.api import ...``. The old import raises an ``ImportError`` that says so. ``import s3pathlib`` now only gives the version info and no longer imports the library (2.x imported everything, and silently left names out when a dependency was missing); submodules such as ``from s3pathlib import utils`` still work.
- Drop support for Python 3.9 and 3.10, the minimum supported version is now Python 3.11. Python 3.11 to 3.14 are supported and tested.
- Remove the ``s3pathlib.compat`` module. It only existed to support old ``smart_open`` versions.
- Raise the minimum dependency versions: ``boto3>=1.41.0``, ``smart-open>=7.0.0,<9.0.0``.
- Remove the runtime dependencies ``pathlib-mate``, ``func-args`` and ``boto-session-manager``. The runtime dependencies are now ``boto3``, ``smart-open``, ``iterproxy`` and ``typing-extensions`` (Python < 3.13 only). If your code imports one of the removed packages, add it to your own dependencies.
- ``S3Path`` objects no longer have a ``__dict__``: every class declares ``__slots__`` (2.x declared it on the base class only, so it had no effect). Setting an attribute that ``S3Path`` does not define, e.g. a typo such as ``p.verison_id = ...``, raises ``AttributeError``. Keep your own data next to the path, e.g. in a ``dict`` keyed by the path.
- ``S3Path.delete_bucket`` no longer clears the metadata snapshot of the path in place (e.g. of a bucket from ``list_buckets``), the same as every other method that changes S3.
- Remove ``s3pathlib.exc.ensure_one_and_only_one_not_none`` and ``s3pathlib.exc.ensure_all_none``; the library no longer uses them.
- Rename ``s3pathlib.exc._S3PathTypeError`` to the public ``s3pathlib.exc.S3PathTypeError``.
- Remove ``S3Path.delete_if_exists``, deprecated since 2.0.1. Use :meth:`~s3pathlib.core.delete.DeleteAPIMixin.delete` instead.
- Remove ``deprecate_v1``, ``deprecate_v2``, ``warn_deprecate`` and ``warn_beta`` from ``s3pathlib.marker``.
- Remove ``S3BucketValidationError``, ``S3KeyValidationError`` and the key charset constants (``safe_key_charset``, ``req_special_handling_key_charset``, ``to_avoid_key_charset``, ``valid_key_charset``) from ``s3pathlib.validate``. Validators now raise :class:`s3pathlib.exc.S3ValidationError`.
- ``s3pathlib`` no longer checks bucket naming rules or the key length itself; S3 is the authority and enforces them when you call the API. ``S3Path(...)``, ``S3Path.from_s3_uri``, ``S3Path.from_s3_arn`` and ``S3Path.from_bucket`` only check the format (a well formed URI / ARN and a non-empty bucket). The ``s3pathlib.validate`` functions are now optional tools that the library does not call.
- ``validate_s3_bucket`` now checks the naming rules for a *new* general purpose bucket, as documented by AWS: it also rejects two adjacent periods, the reserved prefixes ``sthree-`` and ``amzn-s3-demo-``, and the reserved suffixes ``-s3alias``, ``--ol-s3``, ``.mrap``, ``--x-s3`` and ``--table-s3``.
- ``S3Path(...)`` and ``utils.split_s3_uri`` reject a malformed URI such as ``https://bucket/key`` or ``s3:/bucket/key`` with ``S3ValidationError``, instead of silently parsing it into a wrong bucket and key. An empty bucket (e.g. ``S3Path("")``, ``s3://``) also raises ``S3ValidationError`` instead of ``IndexError``.
- Remove ``s3pathlib.utils.validate_s3_bucket`` and ``s3pathlib.utils.validate_s3_key``, two placeholders that did nothing. The real validators are in ``s3pathlib.validate``.
- ``s3pathlib.validate.valid_bucket_charset`` and ``letter_and_number``, two helper sets of ``validate_s3_bucket``, are now private (``_VALID_BUCKET_CHARSET``, ``_LETTER_AND_NUMBER``).
- Remove ``hash_binary``, ``md5_binary``, ``sha256_binary``, ``hash_file`` and ``DEFAULT_CHUNK_SIZE`` from ``s3pathlib.utils``; they were not used by the library. Use the standard library ``hashlib`` instead, e.g. ``hashlib.md5(data).hexdigest()``.
- The low level helpers that were available as ``s3pathlib.api.*`` in 2.x (``is_bucket_exists``, ``upload_dir``, ``paginate_list_objects_v2``, ...) moved to ``s3pathlib.api.better_client.*``.
- Remove the S3 console URL variants from ``S3Path``: ``get_regional_console_url(region)``, ``us_gov_cloud_console_url`` and ``get_regional_us_gov_cloud_console_url(region)``. Use ``S3Path.get_console_url(region=..., partition=...)`` instead, e.g. ``p.get_console_url(partition="aws-us-gov")``. ``S3Path.console_url`` is kept.
- Remove the S3 Select console URLs: ``S3Path.s3_select_console_url``, ``S3Path.get_regional_s3_select_console_url``, ``S3Path.s3_select_us_gov_cloud_console_url``, ``S3Path.get_regional_s3_select_us_gov_cloud_console_url`` and ``s3pathlib.utils.make_s3_select_console_url``. AWS closed Amazon S3 Select to new customers on July 25, 2024 and recommends Amazon Athena or client-side filtering instead.
- Remove the ``is_us_gov_cloud`` argument of ``utils.make_s3_console_url``. Use ``partition="aws-us-gov"`` instead.
- An ``S3Path`` is now always in one of six valid states (file, dir, bucket, relative file, relative dir, void; see ``s3pathlib.core.base``), checked whenever a path is built. As a result:

    - ``S3Path("bucket").to_file()`` raises ``S3PathIsNotFileError`` (a ``TypeError``). Before, it returned a "bucket that is a file", for which ``is_file()`` was ``True`` and ``is_bucket()`` was ``False``.
    - ``S3Path.from_dict`` raises ``S3ValidationError`` for data that is not a valid state, e.g. an empty bucket, a part containing ``/``, a bucket root with ``is_dir=False``, or ``parts`` that is a string instead of a list (``"abc"`` gave ``s3://b/a/b/c``). Before, it built a broken path such as ``s3:///a``. It also raises ``S3ValidationError`` instead of ``KeyError`` / ``TypeError`` when the dict misses a key or is not a dict.
- ``S3Path.change`` rejects arguments that used to silently give a wrong path, with ``ValueError``: ``new_ext`` that is not empty and does not start with ``.`` (``new_ext="png"`` gave ``c.jpg`` -> ``cpng``), ``new_fname`` or ``new_ext`` containing ``/``, an empty ``new_basename`` (it turned the path into its parent dir as a file), and ``new_dirname`` on a path without parent dir (it added a dir). ``new_fname`` / ``new_ext`` on a dir raise ``ValueError`` with a message instead of a bare ``TypeError``.
- ``S3Path.fname`` and ``S3Path.ext`` raise ``S3PathIsNotFileError`` (a ``TypeError``) on anything that is not a file. Before, they raised a bare ``TypeError`` on a dir or a bucket, and a bare ``ValueError`` on the void path.
- ``relative_to`` (and ``-``) is now the exact inverse of ``/``: ``base / target.relative_to(base) == target``. When both paths have the same parts but one is a file and the other a dir (e.g. ``S3Path("b", "a/").relative_to(S3Path("b", "a"))``), it raises ``ValueError``. Before, it returned the void path, and ``base / void`` was not ``target``.
- ``s3pathlib.context`` is renamed to ``s3_context`` (``from s3pathlib.api import s3_context``), and its class ``Context`` to ``S3Context``. ``context`` was too generic and is shadowed by the ``context`` argument of AWS Lambda handlers (``def lambda_handler(event, context)``). The old names ``context`` and ``Context`` are removed.
- ``s3_context`` only holds the default S3 client. Remove ``attach_boto_session``, ``attach_sts_client``, ``boto_ses``, ``sts_client``, ``aws_account_id`` and ``aws_region``. Replace ``context.attach_boto_session(boto_ses)`` with ``s3_context.attach_s3_client(boto_ses.client("s3"))``. For the account id, call ``boto_ses.client("sts").get_caller_identity()["Account"]``; for the region, read ``s3_client.meta.region_name``.
- Rename the ``bsm`` argument of every ``S3Path`` method that calls AWS to ``s3_client``. It only accepts a boto3 S3 client; anything else, such as a ``BotoSesManager`` (accepted in 2.x), raises ``TypeError`` before any call: replace ``bsm=bsm`` with ``s3_client=bsm.s3_client``. The ``better_client`` functions already took ``s3_client``.
- ``better_client.is_bucket_exists`` (and ``S3Path("bucket").exists()``, which uses it) raises ``S3PermissionDenied`` (a ``PermissionError``) when S3 returns 403, i.e. the bucket exists but belongs to another AWS account, or you lack the ``s3:ListBucket`` permission. Before, it raised the ``botocore.exceptions.ClientError`` as is; the ``ClientError`` is now the ``__cause__``.
- ``better_client.head_object`` and ``better_client.is_object_exists`` (and the ``S3Path`` methods built on them, such as ``exists()`` on a file and the metadata properties) raise ``S3PermissionDenied`` when S3 returns 403, even with ``ignore_not_found=True``: no permission is not "not found". Before, they raised the ``botocore.exceptions.ClientError`` as is; it is now the ``__cause__``.
- Rename the misspelled ``ListObjectsV2OutputTypeDefIterproxy.common_prefixs()`` and ``contents_and_common_prefixs()`` (returned by ``better_client.paginate_list_objects_v2``) to ``common_prefixes()`` and ``contents_and_common_prefixes()``, the same names as in ``better_client.list_object_versions``.
- Rename the ``check_sum_algorithm`` argument to ``checksum_algorithm`` in ``S3Path.delete``, ``S3Path.put_bucket_versioning``, ``better_client.delete_dir``, ``better_client.delete_object_versions`` and ``better_client.delete_object_all_versions``, the same name as in every other method and as the boto3 parameter ``ChecksumAlgorithm``. The old name raises ``TypeError``.
- ``better_client.delete_object_versions`` requires ``prefix`` to end with ``/`` (or be ``""`` for the whole bucket), the same as ``better_client.delete_dir``, and raises ``S3ValidationError`` otherwise. A prefix such as ``"data/file.txt"`` also matched ``data/file.txt.bak`` and deleted all its versions. To delete all versions of one object, use the new ``better_client.delete_object_all_versions``.
- ``S3Path.exists(version_id=...)`` and ``S3Path.ensure_not_exists(version_id=...)`` raise ``ValueError`` on a bucket or a folder, before calling AWS. Before, ``version_id`` was silently ignored (e.g. ``S3Path("bucket").exists(version_id="v1")`` was ``True``); it only applies to a file.
- The metadata loaded from S3 on an ``S3Path`` (``size``, ``etag``, ``last_modified_at``, ``version_id``, ``expire_at``, ``metadata``) is now a snapshot of one object version at one moment, see ``s3pathlib.core.metadata``. As a result:

    - ``exists()`` and ``read_bytes()`` / ``read_text()`` only fill an ``S3Path`` that has no metadata yet; they no longer replace loaded metadata. To load the latest metadata, call ``head_object()`` (or ``clear_cache()``).
    - A missing field of a partial snapshot (e.g. the user metadata of a listed object) is loaded from the same object version, not from the latest one. When the object was overwritten after it was listed, it raises the new ``S3ObjectChangedError`` instead of mixing the data of two objects.
    - The properties of a delete marker never call AWS: ``size`` is ``0`` and ``etag``, ``metadata`` and ``expire_at`` are ``None``. Before, ``metadata`` loaded the latest version and raised ``S3FileNotExist``.
    - ``response`` and ``metadata`` return a copy; changing it no longer changes the loaded metadata.
- Remove ``S3Path.update_metadata``, which only raised ``NotImplementedError`` (S3 cannot change the metadata of an object without writing it again). Use ``write_bytes(..., metadata=...)`` or ``copy_file(..., metadata=...)``.
- ``S3Path.iter_objects()`` and ``S3Path.iterdir()`` on a file raise ``S3PathIsNotFolderError`` before calling AWS, the same as ``count_objects()`` and ``calculate_total_size()``. Before, they listed the keys starting with the key of the file, e.g. ``file.txt.bak`` and ``file.txt/...`` for ``file.txt``. To list by a string prefix, use ``better_client.paginate_list_objects_v2(prefix=...)``.
- ``S3Path.iterdir()`` returns the files and the folders in the S3 order (by key, files and folders mixed), the same as ``iter_objects()``. Before, it returned the folders then the files of each page of up to ``batch_size`` entries, so the order changed with the page size.
- ``S3PathIterProxy.filter_by_ext`` raises ``ValueError`` for an extension that is not ``""`` and does not start with ``.`` (e.g. ``"csv"``), which matched nothing.
- Remove the ``ignore_ext``, ``range`` and ``part_number`` arguments of ``S3Path.open``; passing them raises ``TypeError``. None of them ever had an effect: ``ignore_ext`` was removed from smart_open 6, and smart_open sets its own ``Range`` to stream and seek (``range`` was ignored, ``part_number`` failed on AWS). ``open`` reads and writes whole objects; to read part of an object use ``read_bytes(range=...)`` or ``read_bytes(part_number=...)``, to turn off compression use ``compression="disable"``.
- ``S3Path.open`` raises ``ValueError`` for a key containing ``?versionId=`` or ``&versionId=`` (e.g. ``page?versionId=1``); use ``read_bytes`` / ``write_bytes`` for such keys. smart_open 8 takes that part of the URI as a version id and removes it from the key, even when ``version_id`` is given, so writing failed and reading silently read another object; there is no way to escape it. The key is rejected with every smart_open version, so that code does not break when smart_open is upgraded. Other ``?`` in a key still work.
- ``S3Path.open`` raises ``ValueError`` for ``version_id`` in write mode, and for ``content_length``, ``content_md5`` and ``checksum_crc32`` / ``checksum_crc32c`` / ``checksum_sha1`` / ``checksum_sha256`` with ``multipart_upload=True`` (the default), which only ``put_object`` (``multipart_upload=False``) supports. Before, they were silently ignored.
- ``S3Path.copy_file`` returns a new ``S3Path`` of the copy (with ``etag``, ``last_modified_at`` and ``version_id`` from the response), the same as ``write_bytes``; it returned the ``copy_object`` response ``dict`` before.
- Remove the ``content_md5`` argument of ``S3Path.copy_file``, ``copy_dir``, ``copy_to`` and ``move_to``; ``copy_object`` has no such parameter, so passing it always raised ``ParamValidationError``.
- ``S3Path.copy_dir`` and ``S3Path.move_to`` raise ``ValueError`` when the source and target folders overlap (the same folder, or one inside the other, in the same bucket): copying could overwrite source objects before they are copied. ``S3Path.move_to`` also raises ``ValueError`` for a file moved to itself.
- ``S3Path.copy_dir`` (and ``copy_to`` / ``move_to`` on a folder) raise ``ValueError`` for ``copy_source_if_match``, ``copy_source_if_none_match``, ``copy_source_if_modified_since`` and ``copy_source_if_unmodified_since``, which applied to every object (an ETag can match one object only), and ``copy_to`` raises ``ValueError`` for ``version_id`` on a folder, which was ignored.
- ``S3Path.copy_dir`` copies every key under the folder, folder markers included (the marker of the folder itself becomes the marker of the target), so empty folders are copied too; the returned count includes them. Before, folder markers were skipped.
- ``S3Path.delete`` always returns a new ``S3Path`` and no longer changes the path it is called on (see ``s3pathlib.core.metadata``). Before, it returned the path itself with its cached metadata cleared, except for a file with versioning. With versioning, the returned path is the new delete marker; with ``version_id``, the deleted version.
- ``S3Path.delete`` raises ``ValueError`` for ``version_id`` on a folder, or together with ``is_hard_delete=True``; it was ignored.
- ``S3Path.sync``, ``sync_from`` and ``sync_to`` run ``aws s3 sync`` with the identity of the S3 client of the call, like every other method: the credentials and the region of ``s3_client`` or of the client of ``s3_context``, and its endpoint when it is not an AWS endpoint (``--endpoint-url``). Environment variables such as ``AWS_PROFILE`` no longer decide which credentials the command uses; attach a client of that profile instead. Before, the command used the default credentials of the environment and ignored the attached client. See ``s3pathlib.core.sync`` for the limits (temporary credentials are not refreshed during the sync).
- ``S3Path.sync`` raises ``s3pathlib.exc.S3SyncError`` (with the exit code and stderr of the command) instead of ``SystemError`` when the command fails.
- ``S3Path.sync`` raises ``S3PathIsNotFolderError`` for an ``S3Path`` of a file (``aws s3 sync`` syncs folders) and ``S3PathTypeError`` for a relative path or the void path.
- By default (``quiet=True``), ``S3Path.sync`` runs the command with ``--only-show-errors`` instead of ``--quiet``: nothing is printed either way when it succeeds, but ``--quiet`` also hid the error, so a failure had no message.

**Features and Improvements**

- Add the ``s3pathlib.api`` module as the public entry point. Import public names with ``from s3pathlib.api import ...``.
- Add :class:`s3pathlib.exc.S3PathlibError` as the base class of all exceptions raised by ``s3pathlib``, so ``except S3PathlibError`` catches them all.
- Regroup the exception hierarchy: ``S3BucketNotExist``, ``S3FolderNotExist`` and ``S3FileNotExist`` now inherit from ``S3NotExist``; the ``*AlreadyExist`` exceptions inherit from ``S3AlreadyExist``. Every exception still inherits from the same builtin exception as before (``FileNotFoundError``, ``FileExistsError``, ``PermissionError``, ``TypeError``), so existing ``except`` clauses keep working.
- Add :class:`s3pathlib.exc.S3ValidationError`, raised by every validator in ``s3pathlib.validate``. It is also a ``ValueError``, so existing ``except ValueError`` clauses keep working.
- ``validate_s3_uri`` accepts a bucket URI without the trailing slash, e.g. ``s3://bucket``.
- Support S3 ARNs in the ``aws-cn`` (China), ``aws-us-gov`` (GovCloud) and ``aws-eusc`` (European Sovereign Cloud) partitions, in addition to ``aws``:

    - Add :class:`s3pathlib.constants.AwsPartitionEnum` listing the supported partitions.
    - Add :func:`s3pathlib.utils.split_s3_arn`, which returns the partition, bucket and key.
    - Add ``S3Path.get_arn(partition)``. ``S3Path.arn`` still returns the ``aws`` partition ARN.
    - ``S3Path(arn)``, ``S3Path.from_s3_arn`` and ``validate_s3_arn`` accept ARNs from all supported partitions.
- Add the general purpose bucket naming rules to ``s3pathlib.constants`` (``S3_BUCKET_MIN_LENGTH``, ``S3_BUCKET_MAX_LENGTH``, ``S3_BUCKET_RESERVED_PREFIXES``, ``S3_BUCKET_RESERVED_SUFFIXES``) and ``S3_KEY_MAX_BYTES``.
- ``utils.make_s3_console_url`` accepts a ``partition`` argument and supports the China (``console.amazonaws.cn``) and European Sovereign Cloud (``console.amazonaws-eusc.eu``) consoles. The console domains are in ``s3pathlib.constants.AWS_CONSOLE_DOMAIN``.
- Add ``S3Path.get_console_url(region=None, partition="aws")``, the console URL of the path in any region and any supported partition.
- ``S3Path.parents`` supports relative paths and the void path, the same as ``pathlib.PurePath.parents``: the parents of a relative path end with the void path, and the void path has no parents. Before, both raised ``ValueError``.
- Deprecate joining onto a file and using a file as the base of ``relative_to``. ``S3Path("bucket", "folder") / "file.txt"``, ``S3Path("bucket", "folder").joinpath(...)`` and ``S3Path("bucket", "a/b").relative_to(S3Path("bucket", "a"))`` still work, but emit a ``DeprecationWarning``, because a file has no sub path; they will raise ``S3PathIsNotFolderError`` in 4.0.0. This includes chains such as ``S3Path("bucket") / "folder" / "file.txt"``, where ``S3Path("bucket") / "folder"`` is a file. Use a dir: ``S3Path("bucket") / "folder/" / "file.txt"``, ``.to_dir()``, or join all parts at once with ``S3Path("bucket").joinpath("folder", "file.txt")`` or ``S3Path("bucket") / ["folder", "file.txt"]``.
- ``relative_to`` (and ``-``) works between two relative paths, e.g. ``S3Path.make_relpath("a/b").relative_to(S3Path.make_relpath("a/"))``, the same as ``pathlib``. Before, it raised ``ValueError``.
- ``S3Path.is_parent_of`` and ``S3Path.is_prefix_of`` work between two relative paths (the void path is the parent of every relative path). An absolute path and a relative path give ``False``, the same as two buckets. Before, any path without bucket raised ``TypeError``.
- ``S3Path.make_relpath`` accepts relative paths as parts, and follows the same rules as the ``S3Path`` constructor.
- Add ``s3pathlib.api.S3PathDict``, a ``TypedDict`` for the dict returned by ``S3Path.to_dict`` and accepted by ``S3Path.from_dict``.
- ``S3Path() / x`` works and gives ``x`` as a relative path, the same as ``S3Path().joinpath(x)``. The void path is the identity of joining paths. Before, it raised ``TypeError``.
- Add ``s3pathlib.marker.deprecated``, the standard :pep:`702` decorator. Deprecated APIs now emit a ``DeprecationWarning`` that points at the caller, and type checkers / IDEs flag the call sites.
- ``s3_context`` is thread safe: the default S3 client is created at most once, under a lock, and ``attach_s3_client`` replaces the client in one step.
- ``s3_context`` creates the default S3 client when it is first used instead of when ``s3pathlib`` is imported, so importing ``s3pathlib`` has no side effect, and environment variables such as ``AWS_PROFILE`` set after the import are honored.
- Add ``better_client.delete_object_all_versions(s3_client, bucket, key)``, which permanently deletes all versions and delete markers of exactly one key.
- Add ``s3pathlib.exc.S3DeleteObjectsError``, raised when S3 fails to delete some objects of a ``delete_objects`` call; it has the ``errors`` S3 returned and the number of objects deleted so far (``n_deleted``).
- ``S3Path.list_buckets()`` keeps the region of each bucket when S3 returns it, in ``response["BucketRegion"]``. Add ``s3pathlib.constants.S3_LIST_BUCKETS_MAX_BUCKETS``, the page size of ListBuckets (10,000).
- ``S3Path.head_object`` accepts ``version_id``, to load the metadata of one version.
- An ``S3Path`` produced by a call with an explicit client (``s3_client=...``), e.g. by ``iter_objects(s3_client=...)`` or ``head_object(s3_client=...)``, remembers that client and loads its missing metadata with it, instead of the default client of ``s3_context``. The other methods do not use it: without ``s3_client`` they use ``s3_context``, however the path was made. Pickle does not keep the client; ``copy.copy`` / ``copy.deepcopy`` do.
- Add ``s3pathlib.exc.S3ObjectChangedError``.
- ``S3Path.write_bytes`` and ``S3Path.write_text`` accept ``if_match`` and ``if_none_match``, the conditional writes of S3: ``if_none_match="*"`` only writes a new object, ``if_match=<etag>`` only replaces the object if nobody changed it.
- ``S3Path.touch`` makes one conditional ``put_object`` call instead of ``head_object`` + ``put_object``, so it is atomic: an object written by someone else in between is never replaced.
- ``S3Path.upload_file`` returns a new ``S3Path`` of the uploaded object, the same as ``write_bytes``; it returned ``None`` before.
- ``S3Path.copy_file`` (and the other copy methods) with ``overwrite=False`` copy conditionally (``IfNoneMatch="*"``) after checking the target, so on AWS an object written by someone else in between is not replaced either.
- Add the ``quiet`` argument to ``S3Path.sync``, ``sync_from`` and ``sync_to``. The misspelled ``quite`` is deprecated: passing it emits a ``DeprecationWarning``; it will be removed in 4.0.0. When both are given, ``quite`` is used.
- ``S3Path.sync`` supports S3 compatible endpoints (the endpoint of the client is passed to the CLI) and unsigned clients (``--no-sign-request``).
- Add ``s3pathlib.exc.S3SyncError``.
- ``s3pathlib.api`` also exports the exceptions module ``exc`` (e.g. ``except exc.S3FileNotExist``), ``S3PathIterProxy`` (returned by ``iter_objects``, ``iterdir`` and ``list_object_versions``) and ``AwsPartitionEnum`` (for ``get_arn`` / ``get_console_url``), so every public name is available from ``s3pathlib.api``.

**Bugfixes**

- ``S3Path.list_buckets()`` failed with ``S3ValidationError`` when the account had a legacy bucket (created in us-east-1 before March 2018, with uppercase letters or underscores). It now lists every bucket S3 returns. ``S3Path.from_s3_uri``, ``S3Path.from_s3_arn`` and ``S3Path.from_bucket`` also accept legacy bucket names.
- ``utils.make_s3_console_url`` did not URL encode the key, so a key with ``&``, ``#``, ``?``, ``+``, ``%`` or spaces opened the wrong object or none at all.
- ``utils.repr_data_size`` showed ``1048575`` bytes as ``1024.00 KB`` instead of ``1.00 MB``, raised ``KeyError`` above 1024 YB, and accepted negative sizes. It now carries rounding over to the next unit, shows larger sizes in YB, and rejects negative sizes with ``ValueError``.
- ``utils.parse_data_size`` raised a bare ``ValueError`` for a number without unit (e.g. ``"100"``); a bare number now means bytes, and invalid text raises ``ValueError`` with a message.
- ``utils.smart_join_s3_key`` returned ``"/"`` for no parts with ``is_dir=True``; it now returns ``""`` (the bucket root).
- ``utils.grouper_list`` with ``n < 1`` silently returned everything as one list; it now raises ``ValueError``.
- ``validate_s3_key`` rejected valid keys with non-ASCII characters or characters such as ``~`` and ``%``. It now accepts any UTF-8 key.
- ``validate_s3_key`` measured the 1024 limit in characters; it now measures UTF-8 bytes, as S3 does.
- ``validate_s3_bucket`` rejected valid names such as ``1.2.3`` as IP addresses when Python runs with ``-O``.
- ``S3Path(...)`` ignores empty arguments (``""`` or a void path) when deciding whether the path is a file or a directory. Before, ``S3Path("bucket", "a", S3Path())`` was neither a file nor a directory, and ``S3Path("bucket", "a/", "")`` became a file.
- ``S3Path.change`` failed with a bare ``TypeError`` on a dir, a bucket or the void path, even for ``change()`` or ``change(new_bucket=...)``; it now keeps the last part and the type of the path. ``change(new_bucket=..., new_abspath=...)`` ignored ``new_bucket``, and ``new_abspath`` on a relative path raised ``TypeError``; both work now.
- ``S3Path.is_parent_of`` only detected the direct parent: ``S3Path("bkt/a/").is_parent_of(S3Path("bkt/a/b/c"))`` was ``False``. It now detects every ancestor, as documented.
- ``S3Path.is_prefix_of`` compared the URIs with ``<=`` instead of checking a prefix, so ``S3Path("bkt/b").is_prefix_of(S3Path("bkt/c"))`` was ``True``. It now checks that the key starts with the other key, like the S3 ``Prefix``.
- The ``greater_equal`` and ``less_equal`` filters (e.g. ``S3Path.size.greater_equal(1000)``) did an ``==`` comparison; they now do ``>=`` and ``<=``, the same as the ``>=`` and ``<=`` operators.
- A pickled ``S3Path`` carried its cached hash. The hash of a ``str`` differs between Python processes, so after loading it in another process (e.g. with ``multiprocessing``), it was equal to the same path but had a different hash, and ``dict`` / ``set`` lookups missed it. Pickle (and ``copy.copy`` / ``copy.deepcopy``) now saves the path and the metadata, but not the caches, and checks the state when loading. Pickle protocols 0 and 1 work too.
- ``S3Path.is_delete_marker`` called ``head_object`` when no metadata was loaded. That call can never find a delete marker, and it raised ``S3FileNotExist`` for a missing object and also for an object whose latest version is a delete marker; on a relative path it raised ``TypeError``. It now only looks at the metadata loaded by ``list_object_versions`` and never calls the AWS API.
- The ``ensure_*`` validators showed ``None`` in the error message for a relative path or the void path; they now show the path.
- ``S3Path.make_relpath("a", "/")`` is a dir, the same as ``S3Path(S3Path(), "a", "/")``. Before, ``make_relpath`` ignored a trailing ``"/"`` argument and returned a file.
- ``ensure_relpath`` and ``ensure_not_relpath`` had their error messages swapped.
- The parent of a single part relative path (e.g. ``S3Path.make_relpath("a").parent``) and ``S3Path(S3Path(), "/")`` are now the void path. Before, they were a "void path that is a dir", for which ``is_void()`` was ``True`` but ``is_relpath()`` was ``False``.
- Comparing an ``S3Path`` with another type (e.g. ``p == "s3://bucket/key"``, ``p != None``, or ``p in ["a", p]``) raised ``AttributeError``. Now ``==`` returns ``False`` and ``<`` / ``<=`` / ``>`` / ``>=`` raise ``TypeError``, the same as ``pathlib``.
- ``S3Path.parts`` returned the internal list, so changing it changed the path but not its cached hash, which broke ``==`` and ``hash``. It now returns a copy.
- Sorting ``S3Path`` objects put a dir after the part of its content whose name starts with a character smaller than ``/`` (``-``, ``!``, a space, ...): ``sorted([S3Path("b", "a/"), S3Path("b", "a/-x")])`` gave ``a/-x`` before ``a/``, while ``pathlib`` and the S3 list APIs put the dir first. A dir now sorts right after the file of the same name and before all of its content. The hash of an ``S3Path`` changed with it, which does not matter as it is never saved.
- When the default boto session could not be created at import time (e.g. ``AWS_PROFILE`` names an unknown profile), the error was silently ignored and every later API call failed with ``AttributeError: 'NoneType' object has no attribute 'client'``, even after fixing the environment. The error (e.g. ``ProfileNotFound``) is now raised by the first API call, and the next call works once the environment is fixed.
- ``better_client.is_bucket_exists`` recognized "not found" by looking for ``Not Found`` in the error message; it now checks the error code ``404``, as the message of a ``HEAD`` response is not reliable.
- ``better_client.head_object`` with a ``version_id`` that is a delete marker raised ``ClientError`` (S3 answers 405); it now means the object does not exist, the same as when the latest version is a delete marker. So ``is_object_exists(..., version_id=<delete marker>)`` returns ``False``.
- ``better_client.head_object`` recognized "not found" by looking for ``Not Found`` in the error message; it now checks the error code. With moto, a missing bucket raised ``NoSuchBucket`` instead of meaning "not found" as on AWS; both now behave the same.
- ``better_client.paginate_list_objects_v2`` with ``delimiter`` returned more than ``limit`` entries, because ``limit`` only counted the objects, not the folders (common prefixes): ``limit=3`` could return 8 entries. ``limit`` now counts both, the same as S3's ``MaxKeys``. This also applies to ``S3Path.iterdir(limit=...)``, which counts the files and the folders it returns.
- ``better_client.paginate_list_objects_v2`` sent a negative ``limit`` to S3 (which rejects it, while moto silently ignored it); it now raises ``ValueError``. ``limit=0`` returns nothing without calling AWS.
- ``better_client.paginate_list_object_versions`` returned more than ``limit`` entries whenever there were delete markers or folders, because ``limit`` only counted the versions: ``limit=3`` could return 4 entries. ``limit`` now counts versions, delete markers and common prefixes together, the same as S3's ``MaxKeys``. This also applies to ``S3Path.list_object_versions(limit=...)`` and ``better_client.delete_object_versions(limit=...)``.
- ``better_client.paginate_list_object_versions`` sent a negative ``limit`` to S3 (which rejects it, while moto silently ignored it); it now raises ``ValueError``. ``limit=0`` returns nothing without calling AWS.
- **Data loss**: ``S3Path("bucket", "data/file.txt").delete(is_hard_delete=True)`` permanently deleted all versions of every key starting with ``data/file.txt``, such as ``data/file.txt.bak`` and ``data/file.txt2/...``. It now only deletes the versions of ``data/file.txt``.
- ``better_client.delete_dir`` and ``better_client.delete_object_versions`` ignored the objects S3 failed to delete (``delete_objects`` answers HTTP 200 and lists them in ``Errors``) and counted them as deleted. They now raise ``S3DeleteObjectsError`` and stop.
- ``S3Path.list_object_versions()`` yielded the entries of the earlier pages again after each page: 8 versions listed with ``batch_size=2`` gave 20 entries. Each entry is now yielded once, in the S3 order (by key, then newest first), while the pages are fetched.
- ``S3Path("bucket", "file.txt").list_object_versions()`` also listed the versions of every key starting with ``file.txt``, such as ``file.txt.bak``; on a file it now lists the versions of this exact key only. ``limit`` counts the returned entries, and invalid ``limit`` / ``batch_size`` raise ``ValueError`` when the method is called.
- ``S3Path.put_bucket_versioning(enable_mfa_delete=...)`` always failed with ``ParamValidationError``, because it sent ``MFADelete`` as a bool; it also replaced ``Status`` (``enable_mfa_delete=True`` enabled versioning even with ``enable_versioning=False``). It now sends ``MFADelete`` as ``"Enabled"`` / ``"Disabled"`` and keeps ``Status``.
- ``S3Path.create_bucket()`` without ``region`` always asked for ``us-east-1``, which S3 rejects with ``IllegalLocationConstraintException`` when the client is in another region. ``region`` now defaults to ``None``, the region of the S3 client; a client in ``us-east-1`` behaves as before.
- ``S3Path.list_buckets()`` made one ListBuckets request without ``MaxBuckets``, which S3 rejects for an account allowed to have more than 10,000 buckets. It now fetches every page, 10,000 buckets at a time.
- ``S3Path("bucket", "folder/").exists()`` raised ``NoSuchBucket`` when the bucket did not exist, while a file in a missing bucket returned ``False``. A folder in a missing bucket now does not exist either.
- ``S3Path.exists()`` on a path without bucket raised a different error for each kind of path: a bare ``TypeError`` for the void path, a ``TypeError`` from botocore for a relative file, and ``S3PathTypeError`` for a relative folder. It now always raises ``S3PathTypeError`` (still a ``TypeError``) with a message, before calling AWS.
- An ``S3Path`` returned by ``list_object_versions()`` (or by ``write_bytes()`` with versioning) loaded its missing metadata from the latest version, so an old version silently got the size, user metadata and version id of the latest one. It now loads them from its own version.
- ``version_id`` of an ``S3Path`` returned by ``iter_objects()`` / ``iterdir()`` was always ``"null"``, even with versioning, because the list API does not return it. It now loads the real version id.
- ``read_bytes(range=...)`` / ``read_bytes(part_number=...)`` stored the response as the metadata of the object, so ``size`` became the length of the range.
- Reading a metadata property of a bucket, a relative path or the void path raised a botocore error (``ParamValidationError`` or ``TypeError``). It now raises ``S3PathTypeError`` (still a ``TypeError``) before calling AWS. A bucket returned by ``list_buckets()`` still has its ``last_modified_at``.
- ``head_object()`` kept the old metadata when the object no longer existed; it now clears it before raising ``S3FileNotExist``. It also no longer stores ``ResponseMetadata`` in ``response``.
- ``S3Path.get_tags``, ``put_tags`` and ``update_tags`` on a relative file path called AWS with no bucket and failed with a ``TypeError`` from botocore. They now raise ``S3PathTypeError`` (still a ``TypeError``) before calling AWS, the same as for the void path and relative folders.
- ``S3Path.iter_objects(limit=...)`` counted the folder markers (and, with ``recursive=False``, the folders) it skipped, so it returned fewer objects than ``limit``: ``limit=3`` could return 1 object, or none. ``limit`` now counts the returned objects.
- ``S3Path.iterdir()`` returned the folder marker of the folder itself (e.g. ``folder/`` when listing ``folder/``) as an entry, which also took a ``limit`` slot. It is now skipped.
- ``S3PathIterProxy.filter_by_ext`` raised ``S3PathIsNotFileError`` when ``iter_objects()`` returned an object whose key ends with ``/`` and that has content; such a folder now never matches. ``filter_by_ext()`` without extension raises ``ValueError`` with a message.
- ``S3Path.iter_objects()``, ``iterdir()``, ``count_objects()`` and ``calculate_total_size()`` on a relative path or the void path raised a botocore ``TypeError`` (or ``S3PathTypeError`` with a confusing message); they now raise ``S3PathTypeError`` saying it is a relative path. An invalid ``limit`` or ``batch_size`` of ``iter_objects()`` / ``iterdir()`` raises ``ValueError`` when the method is called, not when the iteration starts.
- **Data loss**: ``S3Path.touch(exist_ok=True)`` replaced an existing object with an empty one, although it was documented to do nothing. It now never changes an existing object.
- **Data loss**: ``S3Path.mkdir(exist_ok=True)`` and ``mkdir(parents=True)`` replaced the existing folder marker objects with empty ones, losing their content, and added a version each time with versioning. They now only write the markers that do not exist.
- The ``S3Path`` returned by ``write_bytes`` / ``write_text`` had the user metadata keys in the given case, while S3 stores them in lower case, and no user metadata at all when none was given (so reading ``metadata`` called ``head_object``). It now has the metadata as S3 stores it, ``{}`` when none was given.
- ``read_bytes``, ``read_text``, ``write_bytes``, ``write_text``, ``touch`` and ``mkdir`` on a bucket, a relative path or the void path raised a botocore error (``ParamValidationError`` or ``TypeError``). They now raise ``S3PathTypeError`` (still a ``TypeError``) before calling AWS; ``mkdir`` on a bucket says to use ``create_bucket()``.
- ``S3Path.open("w", ...)`` ignored all the write arguments (``content_type``, ``cache_control``, ``storage_class``, ``acl``, ...) unless ``metadata`` or ``tags`` was also given. They now always take effect.
- ``S3Path.open`` raised ``AttributeError`` for ``mode=None`` and smart_open's ``NotImplementedError`` for ``"w+"`` / ``"r+"``; any mode other than ``r`` / ``rb`` / ``rt`` / ``w`` / ``wb`` / ``wt`` now raises ``ValueError``. A bucket, a relative path or the void path raises ``S3PathTypeError`` instead of a smart_open / botocore error.
- ``S3Path.upload_file`` checks the local path before calling AWS: a missing file raises ``FileNotFoundError`` and a directory raises ``IsADirectoryError``. Before, it first called ``head_object``, and real AWS then raised a confusing ``botocore.exceptions.UnseekableStreamError`` for a directory.
- ``S3Path.upload_file`` and ``S3Path.upload_dir`` on a relative path or the void path raised a botocore ``TypeError`` (with ``overwrite=True``); they now raise ``S3PathTypeError`` before calling AWS.
- **Data loss**: ``S3Path.move_to`` on a file to itself (e.g. to change its metadata) copied the object onto itself, then deleted it. ``S3Path("bucket", "a/").move_to(S3Path("bucket", "a/b/"))`` copied the folder into ``a/b/``, then deleted all of ``a/``, copies included. Both now raise ``ValueError`` before calling AWS.
- **Data loss**: ``S3Path.move_to`` on a folder listed the folder again to delete it, so an object written to it during the move was deleted without being copied. It now deletes exactly the keys it copied.
- ``S3Path.copy_dir`` failed with ``S3PathIsNotFileError`` when the folder had an object whose key ends with ``/`` and that has content.
- ``S3Path.copy_file`` ignored ``content_type``, ``cache_control``, ``content_disposition``, ``content_encoding``, ``content_language``, ``expires_datetime`` and ``website_redirect_location`` unless ``metadata`` was also given, and ``metadata`` reset the ones not given (e.g. ``ContentType`` became ``binary/octet-stream``). Now only what is given changes: the others are read from the source (one more ``head_object`` call, only when one of them is given).
- ``S3Path.copy_file``, ``copy_dir``, ``copy_to`` and ``move_to`` raise ``S3PathTypeError`` for a relative path or the void path, before calling AWS; ``copy_to`` on the void path raised a bare ``TypeError``.
- **Data loss**: ``S3Path("bucket", "file.txt").delete(version_id=v, is_hard_delete=True)`` ignored ``version_id`` and permanently deleted every version of the object, instead of one. It now raises ``ValueError`` before calling AWS.
- The delete marker returned by ``S3Path.delete()`` with versioning had ``is_delete_marker()`` ``False``, and reading its ``size`` raised ``S3FileNotExist``. It is now a delete marker whose properties never call AWS.
- ``S3Path("bucket", "folder/").delete()`` ignored ``check_sum_algorithm`` (it was only used with ``is_hard_delete=True``).
- ``S3Path.delete`` on a relative path raised a botocore ``TypeError``, and a bare ``ValueError`` on the void path; both now raise ``S3PathTypeError`` before calling AWS.
- ``S3Path.sync(..., bsm=s3_client)`` always failed, because it called ``bsm.awscli()``, which only a ``BotoSesManager`` has.
- ``S3Path.sync`` raises ``FileNotFoundError`` with a message telling to install the AWS CLI when the ``aws`` command is not found, and ``ValueError`` with a message when neither path is in S3 (it was a bare ``ValueError``).

**Minor Improvements**

- Support ``smart_open`` 8.x.
- ``S3Path.create_bucket`` is no longer beta and no longer emits a warning.
- Encode spaces in object tags as ``%20`` instead of ``+`` when sending the ``Tagging`` parameter, the same as the official AWS SDKs, so S3 cannot read them as a literal plus sign.
- ``S3Path(...)`` raises ``TypeError`` with a message naming the wrong argument type, instead of a bare ``TypeError``. ``joinpath``, ``/`` and ``make_relpath`` use the same message for an invalid part.
- ``ensure_not_object``, ``ensure_not_file`` and ``ensure_not_dir`` raise ``S3PathTypeError`` (still a ``TypeError``) with a clear message, instead of a bare ``TypeError``.
- ``ensure_relpath`` raises ``S3PathIsNotRelpathError`` and ``ensure_not_relpath`` raises ``S3PathTypeError``, instead of a bare ``TypeError`` (both are still ``TypeError``).
- ``relative_to`` raises ``TypeError`` with a message for an argument that is not an ``S3Path``, instead of ``AttributeError``, and its ``ValueError`` messages say why the path is not under the other one.
- ``S3Path() / [a, b]`` joins the list at once, the same as ``joinpath(a, b)``.
- ``validate_s3_bucket`` lists the invalid characters in sorted order, so the error message is the same in every process.
- ``s3pathlib.tag.parse_tags`` no longer checks its argument: a non-list (e.g. the whole response dict) raises the ``TypeError`` of the failed lookup instead of ``NotImplementedError``.
- ``S3Path.get_arn``, ``S3Path.get_console_url`` and ``utils.make_s3_console_url`` raise ``S3ValidationError`` (still a ``ValueError``) for an unsupported partition, with a message listing the supported ones. An empty region (``""``) also raises ``S3ValidationError`` instead of building a URL whose host starts with ``.``.
- Document every argument of ``S3Path.change`` and the order they are applied in.
- Fix the ``S3Path.to_file`` docstring example, which called ``to_dir``.
- Fix the ``S3Path.key``, ``S3Path.uri`` and ``S3Path.parent`` docstring examples, and the ``-`` docstring, which had the operands swapped.
- ``S3Path.abspath``, ``S3Path.dirpath`` and ``S3Path.root`` raise ``S3PathTypeError`` (still a ``TypeError``) with a message naming the path, and ``S3Path.is_parent_of`` raises ``S3PathIsNotFolderError`` (still a ``TypeError``) on a file.
- Fix the ``S3Path.basename``, ``S3Path.ext`` and ``S3Path.root`` docstrings, which showed wrong values.
- ``repr`` of an ``S3Path`` with a bucket escapes quotes in the key like ``repr`` of a relative path does: ``S3Path("s3://b/it's.txt")`` instead of ``S3Path('s3://b/it's.txt')``. Keys without a quote are unchanged.
- Deleting a filterable property (e.g. ``del p.key``) raises ``AttributeError`` with a clear message, and the messages name the actual class.
- Document every filter of ``FilterableProperty`` (``s3pathlib.core.filterable_property``) and how to combine them.
- Document how ``S3Path`` objects compare (``s3pathlib.core.comparison``): equality ignores the object version, and the order is part by part like ``pathlib``, not the key string order of S3 list APIs.
- Document the six states of an ``S3Path`` (``s3pathlib.core.base``), the full truth table of ``is_void`` / ``is_relpath`` / ``is_bucket`` / ``is_dir`` / ``is_file`` (``s3pathlib.core.is_test``), and what ``bucket`` / ``key`` / ``uri`` / ``arn`` / ``console_url`` return for each kind of path and why (``s3pathlib.core.uri``).
- ``s3_context.attach_s3_client(None)`` raises ``TypeError``. Any other object is accepted as the client (e.g. a stub in tests).
- ``S3FileNotExist`` raised by ``better_client.head_object`` names the version when ``version_id`` is given, and keeps the ``ClientError`` as its ``__cause__``.
- Document that ``better_client.update_bucket_tagging`` and ``better_client.update_object_tagging`` merge like ``dict.update`` and are not atomic, which version ``update_object_tagging`` updates, and which boto3 errors they raise as is (e.g. ``MethodNotAllowed`` for a delete marker). Tag values with spaces, ``+`` and non-ASCII characters are tested against real AWS.
- Document that the result of ``better_client.paginate_list_objects_v2`` can be iterated only once, that its errors are raised when the iteration starts, and that ``prefix`` is a string prefix, not a folder. Fix the ``is_content_an_object`` truth table: a key ending with ``/`` that has data is an object.
- Document that the result of ``better_client.paginate_list_object_versions`` can be iterated only once, that its errors are raised when the iteration starts, and that ``prefix`` is a string prefix. Fix its docstring, which named the wrong return type. ``better_client.list_object_versions.CommonPrefixTypeDefIterproxy`` is now the same class as in ``better_client.list_objects``.
- Deprecate the ``ignore_not_found`` argument of ``better_client.delete_object``: it never had an effect, because S3 never reports a missing key when deleting. Passing it emits a ``DeprecationWarning``; it will be removed in 4.0.0. Document that deleting a missing key in a bucket with versioning adds a delete marker.
- Document how ``better_client.upload_dir`` builds the keys, the ``prefix`` rules (``"data"`` is ``"data/"``, ``""`` is the bucket root), that empty directories are not uploaded, that ``overwrite=False`` checks then uploads (not atomic), and the errors it raises (``S3UploadFailedError`` from boto3 when an upload fails).
- Document the bucket methods of ``S3Path`` (``s3pathlib.core.bucket``): every argument, the boto3 errors they raise as is (e.g. ``BucketAlreadyExists``, ``BucketNotEmpty``, ``NoSuchBucket``), that they reject a path that is not a bucket before calling AWS, and that creating a bucket you already own in ``us-east-1`` succeeds and resets its ACL.
- ``S3Path.ensure_not_exists`` raises ``S3FileAlreadyExist``, ``S3FolderAlreadyExist`` or ``S3BucketAlreadyExist`` depending on the path, instead of ``S3AlreadyExist`` with a message saying "s3 object" for every path. They are subclasses of ``S3AlreadyExist``, so existing ``except`` clauses keep working.
- Document how ``S3Path.exists`` tests a bucket, a file and a folder, which API it calls, and the errors it raises.
- Document the metadata snapshot of ``S3Path`` (``s3pathlib.core.metadata``): where it comes from, when a property calls AWS, which methods change it, and which client loads it.
- Fix the ``expire_at`` docstring: it is the ``Expires`` HTTP header of the object, not the expiration date of a lifecycle rule (which is in ``response["Expiration"]``).
- ``S3Path.put_tags`` returns a copy of the given tags instead of the same ``dict``.
- Document the object tagging methods of ``S3Path`` (``s3pathlib.core.tagging``): ``put_tags({})`` removes all tags, ``update_tags`` is not atomic, which version they change, and the boto3 errors they raise as is. Document that the metadata snapshot of an ``S3Path`` never decides which version an operation works on: without ``version_id``, ``get_tags()``, ``read_bytes()``, ``delete()``, ... work on the latest version.
- Fix the docstrings of ``S3Path.iter_objects`` (``recursive`` was described backwards), ``iterdir`` (``limit`` also counts folders), ``calculate_total_size`` and ``count_objects`` (wrong examples), and document that the results are lazy, can be iterated only once, and carry the metadata from the list API.
- Fix the docstring examples of the read and write methods of ``S3Path`` (``s3pathlib.core.rw``), and document that writing returns a new ``S3Path`` and leaves the original one unchanged, how ``touch`` and ``mkdir`` treat existing objects, and the boto3 errors they raise as is.
- Document ``S3Path.open``: it reads and writes whole objects as streams, how ``compression`` works (inferred from the extension by default), that an exception inside the ``with`` block of a write leaves no partial object (tested), that reading a missing object raises ``OSError`` with the boto3 error as its ``__cause__``, and which arguments smart_open ignores for S3 (``buffering``, ``closefd``, ``opener``).
- Document ``S3Path.upload_file`` and ``S3Path.upload_dir``: ``overwrite=False`` checks then uploads (not atomic, boto3's ``upload_file`` has no conditional write), the allowed ``extra_args``, and the errors they raise. Fix the ``upload_dir`` docstring example, which used a ``path`` argument that does not exist.
- Document the copy methods of ``S3Path`` (``s3pathlib.core.copy``): how metadata and content headers are copied, that ``copy_object`` copies objects up to 5 GB, which version is copied, and the errors they raise as is.
- Document ``S3Path.delete``: what each kind of path and argument deletes, what it returns, that deleting a missing key adds a delete marker with versioning, and that emptying a bucket asks for confirmation.
- Document ``S3Path.sync``: which identity the AWS CLI uses and its limits, every argument, and the errors.
- ``limit=None`` means no limit (the default), the same as leaving it out; it used to raise ``TypeError``. This applies to ``S3Path.iter_objects``, ``iterdir`` and ``list_object_versions``, and to ``better_client.paginate_list_objects_v2``, ``paginate_list_object_versions``, ``delete_dir`` and ``delete_object_versions``.
- ``S3Path.put_bucket_versioning(enable_mfa_delete=None)`` (the default) does not send ``MFADelete``.
- The warning for an uppercase user-defined metadata key says which lowercase key S3 stores instead.

**Miscellaneous**

- Add the ``typing-extensions`` dependency on Python < 3.13, for the ``deprecated`` backport.
- ``utils.ensure_s3_object`` and ``utils.ensure_s3_dir`` raise ``S3ValidationError`` (still a ``ValueError``).
- Fix package metadata: use the SPDX license expression ``Apache-2.0`` and correct the ``classifiers`` field name.
- Switch the build backend from poetry to setuptools, and manage the development environment with mise and uv.
- Add ``s3pathlib.paths`` to centralize project paths, and simplify the test helpers in ``s3pathlib.tests``.
- Disable unit tests that run against real AWS; only the moto-mocked tests run by default.
- Add the idempotent mise tasks ``setup-aws-ci`` and ``teardown-aws-ci``, which create / delete the test S3 buckets, the test IAM user (its policy is built in code, replacing ``.github/workflows/iam-policy.json``) and its GitHub Actions secrets. The AWS profiles used by the tasks and by the tests against real AWS are defined in ``mise.toml``.
- Remove the old test helper ``s3pathlib.tests.mock`` (its ``BaseTest`` used ``cls.bsm``); use ``s3pathlib.tests.mock_aws.BaseTest``, which has ``cls.boto_ses``, ``cls.aws_account_id``, ``cls.aws_region`` and ``self.s3_client``.
- Add ``s3pathlib.tests.mock_aws``, the new base class for tests that call AWS. Every test module runs against moto (``TestMock``) and, when ``S3PATHLIB_TEST_REAL_AWS=true`` (``mise run cov-aws``), against real AWS (``TestRealAws``); ``@mock_only`` / ``@real_aws_only`` mark tests that only work in one mode. Each test gets its own S3 folder, and the real AWS folder of a test class is emptied when it starts. ``mise run setup-aws-ci`` also adds a lifecycle rule that expires the unit test objects after one day. Shared helpers moved to ``s3pathlib.tests.aws_helpers``.
- ``mise run setup-aws-ci`` updates the inline policy of an existing test IAM user (without touching its access key), and the policy allows bucket tagging on temporary buckets.
- The IAM policy of the test user (``mise run setup-aws-ci``) gives full access to the temporary buckets the tests create, named ``s3pathlib-test-tmp-*``.
- ``better_client.upload_dir`` uses the standard library ``pathlib`` instead of ``pathlib_mate``; ``local_dir`` still accepts a ``str``, a ``pathlib.Path`` or a ``pathlib_mate.Path``.
- Remove the local test data folder ``tests/core/test_iter_objects``; the tests write their data to S3 directly.
- The tests of ``S3Path.open`` use ``s3pathlib.tests.mock_aws``; they no longer always run against real AWS (the old test class ignored ``S3PATHLIB_TEST_REAL_AWS``).
- ``s3pathlib.type.PathType`` is ``str | os.PathLike``; the library code no longer imports ``pathlib_mate`` (a ``pathlib_mate.Path`` is still accepted, it is an ``os.PathLike``). ``S3Path.upload_file`` uses the standard library ``pathlib``.
- The tests of ``S3Path.delete`` with versioning also run on moto (moto 5 handles versioned deletes).
- The ``S3Path.sync`` tests run ``aws s3 sync`` end to end, against a moto server in moto mode and against AWS, when the AWS CLI is installed (they are skipped otherwise); the other tests check the command line and its environment. Add ``flask`` and ``flask-cors`` to the test dependencies, for the moto server.
- Remove the ``boto-session-manager`` dependency; the library no longer uses it (``S3Path.sync`` used ``BotoSesManager.awscli()``).
- Regenerate ``requirements*.txt`` with ``mise run export`` (``uv export``), and add ``requirements-mise.txt``. Remove the stale ``requirements-poetry.txt``, ``requirements-automation.txt`` and ``requirements-furo-sphinx-search.txt``, and the old ``.readthedocs.yaml``, which competed with the uv based ``.readthedocs.yml`` (Read the Docs picks either one when both exist).
- The documentation notebooks use the standard library ``pathlib`` instead of ``pathlib_mate``.
- Rewrite the GitHub Actions CI with uv: it runs on every push to ``main`` and ``dev``, on Ubuntu with Python 3.11 to 3.14 and on Windows with Python 3.14, and runs the whole test suite against moto and real AWS. Each workflow run uses its own S3 folder (``GITHUB_RUN_ID``), so concurrent runs do not interfere. Add the Python version classifiers.
- Configure ruff in ``pyproject.toml``: the re-export modules (``s3pathlib.api``, ``better_client.api``, the ``__init__`` modules) ignore ``F401``.
- A test locks the exact set of public names of ``s3pathlib.api``, so any change of the public API is deliberate.
- Every test module that calls AWS uses ``s3pathlib.tests.mock_aws``, so the whole test suite also runs against real AWS (``mise run cov-aws``). Remove the unused test data ``tests/data/``, ``tests/core/test_upload_dir/`` and ``tests/better_client/dummy_data.py``, and their entries in ``s3pathlib.paths``.
- Remove the ``func-args`` dependency; its "not given" value is now the private ``s3pathlib._arg.OPT``. Arguments passed on to boto3 still default to "not given", and ``None`` is still not the same: botocore rejects it with ``ParamValidationError`` (S3 has no ``None`` value), so a condition such as ``if_match=p.etag`` is never silently dropped.





2.3.6 (2025-08-12)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Miscellaneous**

- Fix Author and Maintainer.


2.3.5 (2025-08-10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Miscellaneous**

- No code changes.
- Housekeeping: update docs and clean unused comments.


2.3.4 (2025-07-13)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Bugfixes**

- Fix smart_open version parsing bug that could cause compatibility issues with certain version string formats.

**Miscellaneous**

- Remove unused cached_property import fallback code for Python < 3.8 since the minimum supported Python version is now 3.9.


2.3.3 (2025-06-13)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Bugfixes**

- Relax the requirements of ``func_args>=0.1.1,<1.0.0`` to ``func_args>=0.1.1,<2.0.0`` to allow the latest version of ``func_args`` to be used.

**Miscellaneous**

- Use pywf_open_source code skeleton.


2.3.2 (2025-03-07)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Minor Improvements**

- Allow user to use ``context.attach_s3_client(your_custom_s3_client)`` and ``context.attach_sts_client(your_custom_sts_client)`` to set a custom S3 client, so that you can work with any S3 compatible storage by customizing your own s3 client object.

**Miscellaneous**

- Upgrade moto to 5.X.Y
- Add support to use smart_open 7.X.Y
- Stop testing on Python 3.7


2.3.1 (2024-08-31)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- Add the following public APIs:
    - :class:`S3Path.get_regional_console_url <s3pathlib.core.uri.UriAPIMixin.get_regional_console_url>`
    - :class:`S3Path.get_regional_us_gov_cloud_console_url <s3pathlib.core.uri.UriAPIMixin.get_regional_us_gov_cloud_console_url>`
    - :class:`S3Path.get_regional_s3_select_console_url <s3pathlib.core.uri.UriAPIMixin.get_regional_s3_select_console_url>`
    - :class:`S3Path.get_regional_s3_select_us_gov_cloud_console_url <s3pathlib.core.uri.UriAPIMixin.get_regional_s3_select_us_gov_cloud_console_url>`


2.2.1 (2024-08-10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- Add :class:`s3pathlib.core.metadata.MetadataAPIMixin.response` property method to allow developer to access the underlying ``head_object`` API response.
- Add support for Python 3.12.


2.1.2 (2023-09-10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Minor Improvements**

- now most of the ``S3Path`` methods can take both ``boto3.client("s3")`` or ``boto_session_manager.BotoSesManager(...)`` object for ``bsm`` argument.


2.1.1 (2023-09-03)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- :meth:`~s3pathlib.core.opener.OpenerAPIMixin.open` method now takes full list of ``s3_client.get_object``, ``s3_client.put_object``, ``s3_client.create_multipart_upload`` arguments.

New APIs:

- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.from_bucket`
- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.create_bucket`
- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.delete_bucket`
- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.get_bucket_versioning`
- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.is_versioning_enabled`
- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.is_versioning_suspended`
- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.put_bucket_versioning`
- add :meth:`~s3pathlib.core.bucket.BucketAPIMixin.list_buckets`
- add :class:`~s3pathlib.content_type.ContentTypeEnum`
- add :func:`~s3pathlib.validate.validate_s3_bucket`
- add :func:`~s3pathlib.validate.validate_s3_key`
- add :func:`~s3pathlib.validate.validate_s3_uri`
- add :func:`~s3pathlib.validate.validate_s3_arn`

**Bugfixes**

- :meth:`~s3pathlib.core.delete.DeleteAPIMixin.delete` method now can delete cached metadata correctly.
- fix a bug that :meth:`~s3pathlib.core.opener.OpenerAPIMixin.open` method cannot explicitly set client kwargs.


2.0.1 (2023-04-21)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

Changes:

- most of methods now supports ``version_id`` argument for S3 versioning enabled bucket.
- :meth:`s3pathlib.core.rw.ReadAndWriteAPIMixin.read_bytes` and :meth:`s3pathlib.core.rw.ReadAndWriteAPIMixin.read_text` now support ``version_id`` and full list of ``get_object`` boto3 arguments.
- :meth:`s3pathlib.core.uri.UriAPIMixin.console_url` now take the version id into consideration.
- add :meth:`s3pathlib.core.is_test.IsTestAPIMixin.is_delete_marker` method.
- :meth:`s3pathlib.core.base.BaseS3Path.__new__` now can take S3 URI and ARN directly without using the ``from_s3_uri`` and ``from_s3_arn`` method.

New APIs:

- add ``s3pathlib.better_client`` to the public API, it is a collection of more user friendly boto3 API, with type hint.
- add :meth:`~s3pathlib.core.iter_object_versions.IterObjectVersionsAPIMixin.list_object_versions` method. It will return all objects, all versions, all delete markers in reverse chronological order.
- The :meth:`~s3pathlib.core.is_test.IsTestAPIMixin.is_delete_marker` method can be used to check if the version is a delete marker.
- :meth:`~s3pathlib.core.delete.DeleteAPIMixin.delete`: delete object, directory (recursively), specific object version, object versions, all objects all versions in directory. This API will replace the old :meth:`~s3pathlib.core.delete.DeleteAPIMixin.delete_if_exists` API in 3.X.Y.

**Minor Improvements**

- use moto for unit test.
- add tons of more unit test for edge cases.
- prompt to confirm when delete everything in a bucket.

**Bugfixes**

- fix a bug that should not allow user to set value to attributes like ``bucket``, ``key``.

**Miscellaneous**

- completely rewrite the documentation in Jupyter notebook to provide interactive reading experience.

**Imcompatible Change**

- removed :meth:`~s3pathlib.core.joinpath.JoinPathAPIMixin.join_path`.


1.4.1 (2023-02-16)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- now the following API supports full list of native boto3 argument:
    - ``S3Path.write_bytes``
    - ``S3Path.write_text``
    - ``S3Path.copy_file``
    - ``S3Path.copy_dir``
    - ``S3Path.copy_to``
    - ``S3Path.move_to``
- add many optional argument to the ``S3Path.sync()`` method.


1.3.1 (2022-12-30)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- allow ``and_``, ``or_``, ``not_`` in iterproxy filter.
- allow update ``metadata`` and ``taggings`` in :meth:`~s3pathlib.core.S3Path.copy.CopyAPIMixin.copy_file`, :meth:`~s3pathlib.core.S3Path.copy.CopyAPIMixin.copy_to` and :meth:`~s3pathlib.core.S3Path.copy.CopyAPIMixin.move_to` method.

**Miscellaneous**

- the ``iterproxy.py`` module is taken out and released as a independent project.


1.2.1 (2022-11-20)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- :meth:`~s3pathlib.core.opener.OpenerAPIMixin.open` method now takes ``metadata`` and ``tags`` arguments.
- :meth:`~s3pathlib.core.rw.ReadAndWriteAPIMixin.write_bytes` and :meth:`~s3pathlib.core.rw.ReadAndWriteAPIMixin.write_text`, :meth:`~s3pathlib.core.rw.ReadAndWriteAPIMixin.touch` method now takes ``metadata`` and ``tags`` arguments.
- add :meth:`~s3pathlib.core.sync.SyncAPIMixin.sync`, :meth:`~s3pathlib.core.sync.SyncAPIMixin.sync_from`, :meth:`~s3pathlib.core.sync.SyncAPIMixin.sync_to` method that execute `aws s3 sync <https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html>`_ command

**Minor Improvements**

- raise a warning if there is upper case key used in user defined metadata.


1.1.2 (2022-11-16)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Minor Improvements**

- Refactor ``core.py`` module, split the 2.5k line script into 10+ 100 line module.
- Made the metadata pull more intelligent.

**Bugfixes**

- Fix a bug that the ``S3Path`` constructor should not take concrete S3 object / dir path as the second / third / fourth / ... arguments
- Fix a bug that cannot get the metadata value of the S3Path is created by ``_from_content_dict`` method.


1.1.1 (2022-11-13)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add ``tagging`` management feature
    - add :meth:`~s3pathlib.core.S3Path.get_tags` method
    - add :meth:`~s3pathlib.core.S3Path.put_tags` method
    - add :meth:`~s3pathlib.core.S3Path.update_tags` method
- allow update ``metadata`` and ``taggings`` in :meth:`~s3pathlib.core.S3Path.write_text` and :meth:`~s3pathlib.core.S3Path.write_bytes` method.


1.0.12 (2022-09-10)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add :meth:`s3pathlib.core.S3Path.joinpath` method to mimick ``pathlib.Path.joinpath`` behavior
- add :meth:`s3pathlib.core.S3Path.s3_select_console_url` property
- add :meth:`s3pathlib.core.S3Path.s3_select_us_gov_cloud_console_url` property

**Bugfixes**

- made :meth:`s3pathlib.core.S3Path.console_url` and :meth:`s3pathlib.core.S3Path.us_gov_cloud_console_url` regular property, they should not be ``FilterableProperty``

**Miscellaneous**

- mark :meth:`s3pathlib.core.S3Path.join_path` as deprecated


1.0.11 (2022-07-12)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add the ``__truediv__`` operator override. it is a ``s3path / part1 / part2`` syntax sugar.
- add the ``__sub__`` operator override. it is a ``S3Path("bucket/folder") - S3Path("bucket")`` syntax sugar.

**Minor Improvements**

**Bugfixes**

**Miscellaneous**


1.0.10 (2022-04-30)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Miscellaneous**

- remove the boto session module, now it depends on `boto_session_manager <https://pypi.org/project/boto-session-manager/>`_ library.
- add compatibility support for smart_open >= 6.0 due to the ``ignore_ext`` arg is removed.
- for s3 IO feature, you need ``smart_open>=5.1.x``


1.0.9 (2022-04-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add :meth:`s3pathlib.core.S3Path.boto_ses.BotoSesManager.get_client` method


1.0.8 (2022-04-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Bugfixes**

-  fix import bug in :mod:`s3pathlib.aws` module


1.0.7 (2022-04-17)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Bugfixes**

-  fix import bug in :mod:`s3pathlib.boto_ses` module


1.0.6 (2022-04-13)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add :meth:`s3pathlib.core.S3Path.to_file` method.
- add :meth:`s3pathlib.core.S3Path.to_dir` method.
- add :meth:`s3pathlib.core.S3Path.parents` method.
- add :meth:`s3pathlib.core.S3Path.iterdir` method.
- add :meth:`s3pathlib.core.S3Path.touch` method.
- add :meth:`s3pathlib.core.S3Path.mkdir` method.
- add :class:`s3pathlib.core.S3Path.boto_ses.BotoSesManager` class.

**Minor Improvements**

- add ``bsm`` boto session manager parameter for all method using s3 api.

**Bugfixes**

**Miscellaneous**


1.0.5 (2022-02-06)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add :meth:`s3pathlib.core.S3Path.us_gov_cloud_console_url` property
- add :func:`s3pathlib.utils.parse_data_size` method

**Minor Improvements**

**Bugfixes**

**Miscellaneous**


1.0.4 (2022-01-25)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add :meth:`s3pathlib.core.S3PathIterProxy.equal_to`
- add :meth:`s3pathlib.core.S3PathIterProxy.not_equal_to`
- add :meth:`s3pathlib.core.S3PathIterProxy.greater`
- add :meth:`s3pathlib.core.S3PathIterProxy.greater_equal`
- add :meth:`s3pathlib.core.S3PathIterProxy.less`
- add :meth:`s3pathlib.core.S3PathIterProxy.less_equal`
- add ``recursive = True | False`` argument for :meth:`s3pathlib.util.iter_objects`, so you can ignore files in nested folders
- add ``recursive = True | False`` argument for :meth:`s3pathlib.core.S3Path.iter_objects`, so you can ignore files in nested folders

**Minor Improvements**

**Bugfixes**

- fix a bug that :meth:`s3pathlib.core.S3Path.fname` was a regular property and not filterable

**Miscellaneous**

- Add "S3 Object filter" doc
- Add "File Liked Object IO Object filter" doc


1.0.3 (2022-01-23)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- make :class:`s3pathlib.core.S3Path` a file-like object that support open, read, write.
- add :class:`s3pathlib.core.S3PathIterProxy` that greatly simplify S3 object filtering.
- add :meth:`s3pathlib.core.S3Path.open` method, makes ``S3Path`` a file-like object
- add :meth:`s3pathlib.core.S3Path.write_text`
- add :meth:`s3pathlib.core.S3Path.read_text`
- add :meth:`s3pathlib.core.S3Path.write_bytes`
- add :meth:`s3pathlib.core.S3Path.read_bytes`


1.0.2 (2022-01-21)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- add :meth:`s3pathlib.core.S3Path.from_s3_uri` method.
- add :meth:`s3pathlib.core.S3Path.from_s3_arn` method.
- add :meth:`s3pathlib.core.S3Path.change` method.
- add :meth:`s3pathlib.core.S3Path.is_parent_of` method.
- add :meth:`s3pathlib.core.S3Path.is_prefix_of` method.
- add :meth:`s3pathlib.core.S3Path.dirpath` property.
- add better support to handle auto-created "empty folder" object, add ``include_folder=True`` parameter for :meth:`s3pathlib.core.S3Path.list_objects`, :meth:`s3pathlib.core.S3Path.count_objects`, :meth:`s3pathlib.core.S3Path.calculate_total_size` method.

**Bugfixes**

- fix a bug that AWS S3 will create an invisible object when creating a folder, it should not counts as a valid object for :meth:`s3pathlib.core.S3Path.count_objects`

**Miscellaneous**

- A lot doc improvement.


1.0.1 (2022-01-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Features and Improvements**

- ``s3pathlib.S3Path`` API becomes stable
- ``s3pathlib.utils`` API becomes stable
- ``s3pathlib.context`` API becomes stable

**Miscellaneous**

- First stable release.


0.0.1 (2022-01-17)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- First release, a placeholder release.
