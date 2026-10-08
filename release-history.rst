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

- Drop support for Python 3.9 and 3.10, the minimum supported version is now Python 3.11.
- Remove the ``s3pathlib.compat`` module. It only existed to support old ``smart_open`` versions.
- Raise the minimum dependency versions: ``boto3>=1.41.0``, ``smart-open>=7.0.0,<9.0.0``, ``boto-session-manager>=2.0.1,<3.0.0``, ``func-args>=1.0.2``.
- Remove ``s3pathlib.exc.ensure_one_and_only_one_not_none`` and ``s3pathlib.exc.ensure_all_none``; the library no longer uses them.
- Rename ``s3pathlib.exc._S3PathTypeError`` to the public ``s3pathlib.exc.S3PathTypeError``.
- Remove ``S3Path.delete_if_exists``, deprecated since 2.0.1. Use :meth:`~s3pathlib.core.delete.DeleteAPIMixin.delete` instead.
- Remove ``deprecate_v1``, ``deprecate_v2``, ``warn_deprecate`` and ``warn_beta`` from ``s3pathlib.marker``.
- Remove ``S3BucketValidationError``, ``S3KeyValidationError`` and the key charset constants (``safe_key_charset``, ``req_special_handling_key_charset``, ``to_avoid_key_charset``, ``valid_key_charset``) from ``s3pathlib.validate``. Validators now raise :class:`s3pathlib.exc.S3ValidationError`.
- ``s3pathlib`` no longer checks bucket naming rules or the key length itself; S3 is the authority and enforces them when you call the API. ``S3Path(...)``, ``S3Path.from_s3_uri``, ``S3Path.from_s3_arn`` and ``S3Path.from_bucket`` only check the format (a well formed URI / ARN and a non-empty bucket). The ``s3pathlib.validate`` functions are now optional tools that the library does not call.
- ``validate_s3_bucket`` now checks the naming rules for a *new* general purpose bucket, as documented by AWS: it also rejects two adjacent periods, the reserved prefixes ``sthree-`` and ``amzn-s3-demo-``, and the reserved suffixes ``-s3alias``, ``--ol-s3``, ``.mrap``, ``--x-s3`` and ``--table-s3``.
- ``S3Path(...)`` and ``utils.split_s3_uri`` reject a malformed URI such as ``https://bucket/key`` or ``s3:/bucket/key`` with ``S3ValidationError``, instead of silently parsing it into a wrong bucket and key. An empty bucket (e.g. ``S3Path("")``, ``s3://``) also raises ``S3ValidationError`` instead of ``IndexError``.
- Remove ``s3pathlib.utils.validate_s3_bucket`` and ``s3pathlib.utils.validate_s3_key``, two placeholders that did nothing. The real validators are in ``s3pathlib.validate``.
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
- ``better_client.is_bucket_exists`` (and ``S3Path("bucket").exists()``, which uses it) raises ``S3PermissionDenied`` (a ``PermissionError``) when S3 returns 403, i.e. the bucket exists but belongs to another AWS account, or you lack the ``s3:ListBucket`` permission. Before, it raised the ``botocore.exceptions.ClientError`` as is; the ``ClientError`` is now the ``__cause__``.
- ``better_client.head_object`` and ``better_client.is_object_exists`` (and the ``S3Path`` methods built on them, such as ``exists()`` on a file and the metadata properties) raise ``S3PermissionDenied`` when S3 returns 403, even with ``ignore_not_found=True``: no permission is not "not found". Before, they raised the ``botocore.exceptions.ClientError`` as is; it is now the ``__cause__``.
- Rename the misspelled ``ListObjectsV2OutputTypeDefIterproxy.common_prefixs()`` and ``contents_and_common_prefixs()`` (returned by ``better_client.paginate_list_objects_v2``) to ``common_prefixes()`` and ``contents_and_common_prefixes()``, the same names as in ``better_client.list_object_versions``.
- ``better_client.delete_object_versions`` requires ``prefix`` to end with ``/`` (or be ``""`` for the whole bucket), the same as ``better_client.delete_dir``, and raises ``S3ValidationError`` otherwise. A prefix such as ``"data/file.txt"`` also matched ``data/file.txt.bak`` and deleted all its versions. To delete all versions of one object, use the new ``better_client.delete_object_all_versions``.

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
- When the default boto session could not be created at import time (e.g. ``AWS_PROFILE`` names an unknown profile), the error was silently ignored and every later API call failed with ``AttributeError: 'NoneType' object has no attribute 'client'``, even after fixing the environment. The error (e.g. ``ProfileNotFound``) is now raised by the first API call, and the next call works once the environment is fixed.
- ``better_client.is_bucket_exists`` recognized "not found" by looking for ``Not Found`` in the error message; it now checks the error code ``404``, as the message of a ``HEAD`` response is not reliable.
- ``better_client.head_object`` with a ``version_id`` that is a delete marker raised ``ClientError`` (S3 answers 405); it now means the object does not exist, the same as when the latest version is a delete marker. So ``is_object_exists(..., version_id=<delete marker>)`` returns ``False``.
- ``better_client.head_object`` recognized "not found" by looking for ``Not Found`` in the error message; it now checks the error code. With moto, a missing bucket raised ``NoSuchBucket`` instead of meaning "not found" as on AWS; both now behave the same.
- ``better_client.paginate_list_objects_v2`` with ``delimiter`` returned more than ``limit`` entries, because ``limit`` only counted the objects, not the folders (common prefixes): ``limit=3`` could return 8 entries. ``limit`` now counts both, the same as S3's ``MaxKeys``. This also applies to ``S3Path.iterdir(limit=...)`` and ``S3Path.iter_objects(recursive=False, limit=...)``.
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

**Minor Improvements**

- Support ``smart_open`` 8.x.
- Support ``boto_session_manager`` 2.x, which moved ``BotoSesManager`` to ``boto_session_manager.api``.
- ``S3Path.create_bucket`` is no longer beta and no longer emits a warning.
- Encode spaces in object tags as ``%20`` instead of ``+`` when sending the ``Tagging`` parameter, the same as the official AWS SDKs, so S3 cannot read them as a literal plus sign.
- ``S3Path(...)`` raises ``TypeError`` with a message naming the wrong argument type, instead of a bare ``TypeError``. ``joinpath``, ``/`` and ``make_relpath`` use the same message for an invalid part.
- ``ensure_not_object``, ``ensure_not_file`` and ``ensure_not_dir`` raise ``S3PathTypeError`` (still a ``TypeError``) with a clear message, instead of a bare ``TypeError``.
- ``ensure_relpath`` raises ``S3PathIsNotRelpathError`` and ``ensure_not_relpath`` raises ``S3PathTypeError``, instead of a bare ``TypeError`` (both are still ``TypeError``).
- ``relative_to`` raises ``TypeError`` with a message for an argument that is not an ``S3Path``, instead of ``AttributeError``, and its ``ValueError`` messages say why the path is not under the other one.
- ``S3Path() / [a, b]`` joins the list at once, the same as ``joinpath(a, b)``.
- ``S3Path.get_arn``, ``S3Path.get_console_url`` and ``utils.make_s3_console_url`` raise ``S3ValidationError`` (still a ``ValueError``) for an unsupported partition, with a message listing the supported ones. An empty region (``""``) also raises ``S3ValidationError`` instead of building a URL whose host starts with ``.``.
- Document every argument of ``S3Path.change`` and the order they are applied in.
- Fix the ``S3Path.to_file`` docstring example, which called ``to_dir``.
- Fix the ``S3Path.key``, ``S3Path.uri`` and ``S3Path.parent`` docstring examples, and the ``-`` docstring, which had the operands swapped.
- ``S3Path.abspath``, ``S3Path.dirpath`` and ``S3Path.root`` raise ``S3PathTypeError`` (still a ``TypeError``) with a message naming the path, and ``S3Path.is_parent_of`` raises ``S3PathIsNotFolderError`` (still a ``TypeError``) on a file.
- Fix the ``S3Path.basename``, ``S3Path.ext`` and ``S3Path.root`` docstrings, which showed wrong values.
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

**Miscellaneous**

- Add the ``typing-extensions`` dependency on Python < 3.13, for the ``deprecated`` backport.
- ``utils.ensure_s3_object`` and ``utils.ensure_s3_dir`` raise ``S3ValidationError`` (still a ``ValueError``).
- Fix package metadata: use the SPDX license expression ``Apache-2.0`` and correct the ``classifiers`` field name.
- Switch the build backend from poetry to setuptools, and manage the development environment with mise and uv.
- Add ``s3pathlib.paths`` to centralize project paths, and simplify the test helpers in ``s3pathlib.tests``.
- Disable unit tests that run against real AWS; only the moto-mocked tests run by default.
- Add the idempotent mise tasks ``setup-aws-ci`` and ``teardown-aws-ci``, which create / delete the test S3 buckets, the test IAM user (its policy is built in code, replacing ``.github/workflows/iam-policy.json``) and its GitHub Actions secrets. The AWS profiles used by the tasks and by the tests against real AWS are defined in ``mise.toml``.
- The test helper ``s3pathlib.tests.mock.BaseTest`` no longer uses ``boto_session_manager``: ``cls.bsm`` is replaced by ``cls.boto_ses``, ``cls.aws_account_id`` and ``cls.aws_region``, and the S3 client is ``self.s3_client`` (``s3_context.s3_client``).
- Add ``s3pathlib.tests.mock_aws``, the new base class for tests that call AWS. Every test module runs against moto (``TestMock``) and, when ``S3PATHLIB_TEST_REAL_AWS=true`` (``mise run cov-aws``), against real AWS (``TestRealAws``); ``@mock_only`` / ``@real_aws_only`` mark tests that only work in one mode. Each test gets its own S3 folder, and the real AWS folder of a test class is emptied when it starts. ``mise run setup-aws-ci`` also adds a lifecycle rule that expires the unit test objects after one day. Shared helpers moved to ``s3pathlib.tests.aws_helpers``.
- ``mise run setup-aws-ci`` updates the inline policy of an existing test IAM user (without touching its access key), and the policy allows bucket tagging on temporary buckets.
- The IAM policy of the test user (``mise run setup-aws-ci``) gives full access to the temporary buckets the tests create, named ``s3pathlib-test-tmp-*``.
- ``better_client.upload_dir`` uses the standard library ``pathlib`` instead of ``pathlib_mate``; ``local_dir`` still accepts a ``str``, a ``pathlib.Path`` or a ``pathlib_mate.Path``.





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
