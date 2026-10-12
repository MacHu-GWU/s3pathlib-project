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


3.0.0 (2026-10-12)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Why 3.0.0**

s3pathlib started in January 2022 (1.x) and grew through 2.x for three years. Each release added features on top of what was there, and the library collected technical debt that every new feature had to work around:

- *A flat namespace and glue code.* Everything was imported from the top level ``s3pathlib``, with the errors of a missing dependency swallowed. Behind it sat three third party helpers (``boto-session-manager`` for the ``bsm`` argument, ``func-args`` for the "not given" value, ``pathlib-mate``), a compatibility layer for old ``smart_open`` versions, home made deprecation helpers, and a global ``context`` that managed a boto session.
- *Features the world moved on from.* Amazon S3 Select was closed to new customers, the console URL had one property per partition, and ARNs and URLs only knew the ``aws`` partition.
- *Behavior that was never defined.* Arguments were accepted and silently ignored, an ``S3Path`` could be in states that mean nothing (a "bucket that is a file"), wrong arguments raised a bare ``TypeError``, listing a file listed every key with that string prefix, and the cached metadata could describe a different object version than the one you held. Several of these lost or hid data.
- *An old toolchain.* Python 3.9 and 3.10, poetry, and type hints of the old style.

3.0.0 pays this debt off at once, instead of carrying it into the next years. It is a breaking release on purpose: it drops the old way rather than keep it next to the new one.

- The library is built on boto3 alone: a plain boto3 S3 client is the only thing you pass in (``s3_client``), and the errors of AWS calls are raised as boto3 raises them, unless s3pathlib has a rule or feature of its own.
- Every ``S3Path`` is in one of six valid states, and a method either does what its arguments say or raises; nothing is silently ignored.
- One public entry point, ``s3pathlib.api``, plus ``s3pathlib.api.better_client`` for the thin wrappers of boto3; Python 3.11 and newer, with modern type hints and standard :pep:`702` deprecations.
- The new behavior is documented in the docstrings and tested: the whole library is covered by a large test suite (100% branch coverage) that runs against moto and, on CI, against real AWS on Linux and Windows (Python 3.11 to 3.14).

The ``S3Path`` API still looks like ``pathlib``, so most code only needs the changed import and ``bsm=`` renamed to ``s3_client=``. Go through **Breaking Changes** below for the rest; they are grouped by topic and each says what to change.

**Breaking Changes**

- **Imports.** Import public names with ``from s3pathlib.api import ...``. The top level names of ``s3pathlib`` (``S3Path``, ``s3_context``, ``ContentTypeEnum``, ``validate_s3_bucket`` / ``key`` / ``uri`` / ``arn``, ``and_``, ``or_``, ``not_``) are removed, and the old import raises an ``ImportError`` that says so. ``import s3pathlib`` only gives the version info and no longer imports the library (2.x imported everything, and silently left names out when a dependency was missing); submodules such as ``from s3pathlib import utils`` still work. The low level helpers that were ``s3pathlib.api.*`` in 2.x (``is_bucket_exists``, ``upload_dir``, ``paginate_list_objects_v2``, ...) moved to ``s3pathlib.api.better_client.*``.
- **Python and dependencies.** Drop Python 3.9 and 3.10; Python 3.11 to 3.14 are supported and tested. Raise the minimum versions to ``boto3>=1.41.0`` and ``smart-open>=7.0.0,<9.0.0``. The runtime dependencies are now ``boto3``, ``smart-open``, ``iterproxy`` and ``typing-extensions`` (Python < 3.13 only); ``pathlib-mate``, ``func-args`` and ``boto-session-manager`` are removed, so add them to your own dependencies if your code imports them. Remove the ``s3pathlib.compat`` module, which only supported old ``smart_open`` versions.
- **No ``__dict__``.** Every ``S3Path`` class declares ``__slots__`` (2.x declared it on the base class only, so it had no effect). Setting an attribute that ``S3Path`` does not define, e.g. a typo such as ``p.verison_id = ...``, raises ``AttributeError``. Keep your own data next to the path, e.g. in a ``dict`` keyed by the path.
- **Clients.** Rename ``s3pathlib.context`` to ``s3_context`` (``from s3pathlib.api import s3_context``) and its class ``Context`` to ``S3Context``: ``context`` is shadowed by the ``context`` argument of AWS Lambda handlers (``def lambda_handler(event, context)``). ``s3_context`` only holds the default S3 client: remove ``attach_boto_session``, ``attach_sts_client``, ``boto_ses``, ``sts_client``, ``aws_account_id`` and ``aws_region``. Replace ``context.attach_boto_session(boto_ses)`` with ``s3_context.attach_s3_client(boto_ses.client("s3"))``; get the account id with ``boto_ses.client("sts").get_caller_identity()["Account"]`` and the region from ``s3_client.meta.region_name``. Rename the ``bsm`` argument of every ``S3Path`` method that calls AWS to ``s3_client``. It only accepts a boto3 S3 client; anything else, such as a ``BotoSesManager`` (accepted in 2.x), raises ``TypeError`` before any call: replace ``bsm=bsm`` with ``s3_client=bsm.s3_client``.
- **Exceptions and validation.**

  - Validators raise :class:`s3pathlib.exc.S3ValidationError` (a ``ValueError``): remove ``S3BucketValidationError``, ``S3KeyValidationError`` and the key charset constants (``safe_key_charset``, ``req_special_handling_key_charset``, ``to_avoid_key_charset``, ``valid_key_charset``) from ``s3pathlib.validate``. ``utils.ensure_s3_object`` and ``ensure_s3_dir`` raise it too.
  - Remove ``s3pathlib.exc.ensure_one_and_only_one_not_none`` and ``ensure_all_none``, and the two placeholders ``s3pathlib.utils.validate_s3_bucket`` and ``validate_s3_key`` that did nothing. Rename ``s3pathlib.exc._S3PathTypeError`` to the public ``S3PathTypeError``. ``valid_bucket_charset`` and ``letter_and_number`` of ``s3pathlib.validate`` are now private.
  - ``s3pathlib`` no longer checks bucket naming rules or the key length itself; S3 enforces them when you call the API. ``S3Path(...)``, ``from_s3_uri``, ``from_s3_arn`` and ``from_bucket`` only check the format (a well formed URI / ARN and a non-empty bucket). The functions of ``s3pathlib.validate`` are optional tools the library does not call. ``validate_s3_bucket`` now checks the rules for a *new* general purpose bucket as documented by AWS: it also rejects two adjacent periods, the reserved prefixes ``sthree-`` and ``amzn-s3-demo-``, and the reserved suffixes ``-s3alias``, ``--ol-s3``, ``.mrap``, ``--x-s3`` and ``--table-s3``.
  - ``S3Path(...)`` and ``utils.split_s3_uri`` reject a malformed URI such as ``https://bucket/key`` or ``s3:/bucket/key`` with ``S3ValidationError``, instead of silently parsing it into a wrong bucket and key. An empty bucket (``S3Path("")``, ``s3://``) raises it too, instead of ``IndexError``.
  - ``better_client.is_bucket_exists``, ``head_object`` and ``is_object_exists`` (and the ``S3Path`` methods built on them: ``exists()``, the metadata properties, ...) raise ``S3PermissionDenied`` (a ``PermissionError``) when S3 answers 403: the bucket belongs to another account, or you lack the permission. This holds even with ``ignore_not_found=True``, as no permission is not "not found". The ``ClientError`` is now the ``__cause__``.

- **Path model.** An ``S3Path`` is always in one of six valid states (file, dir, bucket, relative file, relative dir, void; see ``s3pathlib.core.base``), checked whenever a path is built.

  - ``S3Path("bucket").to_file()`` raises ``S3PathIsNotFileError`` (a ``TypeError``); it used to return a "bucket that is a file".
  - ``S3Path.from_dict`` raises ``S3ValidationError`` for data that is not a valid state (an empty bucket, a part containing ``/``, a bucket root with ``is_dir=False``, ``parts`` that is a string), and for a missing key or a non-dict, instead of building a broken path such as ``s3:///a`` or raising ``KeyError`` / ``TypeError``.
  - ``S3Path.change`` rejects with ``ValueError`` what used to give a silently wrong path: a ``new_ext`` that is not empty and does not start with ``.`` (``new_ext="png"`` turned ``c.jpg`` into ``cpng``), ``new_fname`` or ``new_ext`` containing ``/``, an empty ``new_basename``, and ``new_dirname`` on a path without parent dir. ``new_fname`` / ``new_ext`` on a dir raise ``ValueError`` with a message instead of a bare ``TypeError``.
  - ``fname`` and ``ext`` raise ``S3PathIsNotFileError`` on anything that is not a file (a bare ``TypeError`` on a dir or a bucket and a bare ``ValueError`` on the void path before).
  - ``relative_to`` (and ``-``) is the exact inverse of ``/``: ``base / target.relative_to(base) == target``. When both paths have the same parts but one is a file and the other a dir (``S3Path("b", "a/").relative_to(S3Path("b", "a"))``), it raises ``ValueError``; it used to return the void path.
  - ``exists(version_id=...)`` and ``ensure_not_exists(version_id=...)`` raise ``ValueError`` on a bucket or a folder, before calling AWS; ``version_id`` was silently ignored (``S3Path("bucket").exists(version_id="v1")`` was ``True``).
  - Remove ``S3Path.delete_if_exists`` (deprecated since 2.0.1; use ``delete``), ``S3Path.update_metadata`` (it only raised ``NotImplementedError``; use ``write_bytes(..., metadata=...)`` or ``copy_file(..., metadata=...)``), and ``delete_bucket`` no longer clears the metadata snapshot of the path in place.

- **Metadata snapshot.** The metadata loaded from S3 on an ``S3Path`` (``size``, ``etag``, ``last_modified_at``, ``version_id``, ``expire_at``, ``metadata``) is a snapshot of one object version at one moment, see ``s3pathlib.core.metadata``.

  - ``exists()`` and ``read_bytes()`` / ``read_text()`` only fill an ``S3Path`` that has no metadata yet; they no longer replace loaded metadata. To load the latest metadata, call ``head_object()`` (or ``clear_cache()``).
  - A missing field of a partial snapshot (e.g. the user metadata of a listed object) is loaded from the same object version, not the latest one. When the object was overwritten after it was listed, the new ``S3ObjectChangedError`` is raised instead of mixing the data of two objects.
  - The properties of a delete marker never call AWS: ``size`` is ``0``, and ``etag``, ``metadata`` and ``expire_at`` are ``None`` (``metadata`` used to load the latest version and raise ``S3FileNotExist``).
  - ``response`` and ``metadata``, and the result of ``head_object()``, are copies: changing them no longer changes the loaded metadata.

- **Listing.**

  - ``iter_objects()`` and ``iterdir()`` on a file raise ``S3PathIsNotFolderError`` before calling AWS, like ``count_objects()`` and ``calculate_total_size()``; they used to list the keys that start with the key of the file (``file.txt.bak``, ``file.txt/...``). To list by a string prefix, use ``better_client.paginate_list_objects_v2(prefix=...)``.
  - ``iterdir()`` returns files and folders in the S3 order (by key, mixed), like ``iter_objects()``; the order used to change with ``batch_size``.
  - ``iter_objects``, ``iterdir`` and ``list_object_versions`` raise ``S3ValidationError`` while iterating when S3 returns a key that ``S3Path`` cannot represent (consecutive ``/`` such as ``a//b``, or a leading ``/``). ``S3Path`` joins and drops those ``/``, so the listed path was the path of *another* key (``a/b``) with the snapshot of the first one, and ``delete()`` deleted the wrong object. List such keys with ``better_client`` or boto3; ``copy_dir``, ``move_to`` and ``delete`` of a folder work on the keys S3 returns and are not affected.
  - ``S3PathIterProxy.filter_by_ext`` raises ``ValueError`` for an extension that is not ``""`` and does not start with ``.`` (``"csv"``), which matched nothing.
  - ``better_client.delete_object_versions`` requires ``prefix`` to end with ``/`` (or be ``""`` for the whole bucket), like ``delete_dir``, and raises ``S3ValidationError`` otherwise: ``"data/file.txt"`` also matched ``data/file.txt.bak`` and deleted all its versions. To delete all versions of one object, use the new ``better_client.delete_object_all_versions``.
  - Rename the misspelled ``common_prefixs()`` and ``contents_and_common_prefixs()`` of the result of ``better_client.paginate_list_objects_v2`` to ``common_prefixes()`` and ``contents_and_common_prefixes()``.

- **Open.**

  - Remove the ``ignore_ext``, ``range`` and ``part_number`` arguments of ``S3Path.open`` (passing them raises ``TypeError``). None had an effect: ``ignore_ext`` was removed from smart_open 6, and smart_open sets its own ``Range`` to stream and seek. ``open`` reads and writes whole objects; to read a part use ``read_bytes(range=...)`` / ``read_bytes(part_number=...)``, to turn off compression use ``compression="disable"``.
  - A key containing ``?versionId=`` or ``&versionId=`` (``page?versionId=1``) raises ``ValueError``; use ``read_bytes`` / ``write_bytes``. smart_open 8 takes that part of the URI as a version id and removes it from the key, even when ``version_id`` is given, so writing failed and reading silently read another object. The key is rejected with every smart_open version, so code does not break when smart_open is upgraded. Other ``?`` in a key still work.
  - Arguments that were silently ignored when writing now raise ``ValueError``: ``version_id``; ``content_length``, ``content_md5`` and ``checksum_crc32`` / ``checksum_crc32c`` / ``checksum_sha1`` / ``checksum_sha256`` with ``multipart_upload=True`` (the default), which only ``put_object`` (``multipart_upload=False``) supports; and the read arguments ``if_modified_since``, ``if_unmodified_since``, ``response_*`` and ``checksum_mode``. ``if_match`` and ``if_none_match`` now work with ``multipart_upload=False`` (``if_none_match="*"`` used to replace an existing object without an error) and raise ``ValueError`` with the default multipart upload. A failed condition raises ``PreconditionFailed`` as the ``__cause__`` of smart_open's ``ValueError``.

- **Copy.**

  - ``copy_file`` returns a new ``S3Path`` of the copy (with ``etag``, ``last_modified_at`` and ``version_id`` from the response), like ``write_bytes``; it returned the ``copy_object`` response ``dict``.
  - Copying a missing source (``copy_file``, ``copy_to``, ``move_to``) always raises ``S3FileNotExist``, also for a missing ``version_id``. It was ``NoSuchKey``, and ``S3FileNotExist`` once a header or ``metadata`` was given; other errors of ``copy_object`` are still raised as is.
  - Remove the ``content_md5`` argument of ``copy_file``, ``copy_dir``, ``copy_to`` and ``move_to``: ``copy_object`` has no such parameter, so it always raised ``ParamValidationError``.
  - ``copy_dir`` and ``move_to`` raise ``ValueError`` when the source and target folders overlap (the same folder, or one inside the other, in the same bucket), as copying could overwrite source objects before they are copied; ``move_to`` also raises it for a file moved to itself. A folder rejects ``copy_source_if_match``, ``copy_source_if_none_match``, ``copy_source_if_modified_since`` and ``copy_source_if_unmodified_since`` (they applied to every object, and an ETag matches one object only), and ``copy_to`` rejects ``version_id`` on a folder (it was ignored).
  - ``copy_dir`` copies every key under the folder, folder markers included (the marker of the folder itself becomes the marker of the target), so empty folders are copied; the returned count includes them. The marker is skipped when the target is a bucket, which has none.

- **Delete.** ``delete`` always returns a new ``S3Path`` and no longer changes the path it is called on: with versioning, the returned path is the new delete marker, or the deleted version when ``version_id`` is given. It used to return the path itself with its cached metadata cleared. ``delete`` raises ``ValueError`` for ``version_id`` on a folder or together with ``is_hard_delete=True`` (it was ignored). Rename the ``check_sum_algorithm`` argument to ``checksum_algorithm`` in ``S3Path.delete``, ``S3Path.put_bucket_versioning``, ``better_client.delete_dir``, ``delete_object_versions`` and ``delete_object_all_versions``, as in every other method and in boto3; the old name raises ``TypeError``.
- **Sync.**

  - ``sync``, ``sync_from`` and ``sync_to`` run ``aws s3 sync`` with the identity of the S3 client of the call, like every other method: its credentials and region, and its endpoint when it is not an AWS endpoint. Environment variables such as ``AWS_PROFILE`` no longer decide the credentials; attach a client of that profile instead. The command used the default credentials of the environment and ignored the attached client. See ``s3pathlib.core.sync`` for the limits (temporary credentials are not refreshed during the sync).
  - A failed command raises ``s3pathlib.exc.S3SyncError`` (with the exit code and stderr) instead of ``SystemError``. A file raises ``S3PathIsNotFolderError`` and a relative path or the void path ``S3PathTypeError``, as ``aws s3 sync`` syncs folders.
  - By default (``quiet=True``) the command runs with ``--only-show-errors`` instead of ``--quiet``: nothing is printed either way on success, but ``--quiet`` also hid the error.
  - All ``--exclude`` come before all ``--include`` (the CLI lets the later filter win), so ``exclude="*", include="*.csv"`` syncs the csv files; it synced nothing, as ``--include`` came first.

- **Console URLs and S3 Select.** Remove ``S3Path.get_regional_console_url(region)``, ``us_gov_cloud_console_url`` and ``get_regional_us_gov_cloud_console_url(region)``; use ``S3Path.get_console_url(region=..., partition=...)``, e.g. ``p.get_console_url(partition="aws-us-gov")``. ``console_url`` is kept. Remove the ``is_us_gov_cloud`` argument of ``utils.make_s3_console_url`` (use ``partition="aws-us-gov"``). Remove the S3 Select console URLs (``s3_select_console_url``, ``get_regional_s3_select_console_url``, ``s3_select_us_gov_cloud_console_url``, ``get_regional_s3_select_us_gov_cloud_console_url`` and ``utils.make_s3_select_console_url``): AWS closed Amazon S3 Select to new customers on July 25, 2024.
- **Other removals.** Remove ``deprecate_v1``, ``deprecate_v2``, ``warn_deprecate`` and ``warn_beta`` from ``s3pathlib.marker`` (use the new ``deprecated``), and ``hash_binary``, ``md5_binary``, ``sha256_binary``, ``hash_file`` and ``DEFAULT_CHUNK_SIZE`` from ``s3pathlib.utils`` (use the standard library ``hashlib``).

**Features and Improvements**

- **Public API.** Add the ``s3pathlib.api`` module as the public entry point. It exports every public name, including the ``exc`` module, ``S3PathIterProxy`` (returned by ``iter_objects``, ``iterdir`` and ``list_object_versions``), ``AwsPartitionEnum`` and ``S3PathDict`` (a ``TypedDict`` for the dict of ``to_dict`` / ``from_dict``). A test locks the set of public names, so any change is deliberate.
- **Exceptions.** Add :class:`s3pathlib.exc.S3PathlibError`, the base class of every exception raised by ``s3pathlib``. The hierarchy is regrouped: ``S3BucketNotExist``, ``S3FolderNotExist`` and ``S3FileNotExist`` inherit from ``S3NotExist``, the ``*AlreadyExist`` ones from ``S3AlreadyExist``; each still inherits the same builtin exception as before, so existing ``except`` clauses keep working. New: ``S3ValidationError``, ``S3ObjectChangedError``, ``S3SyncError``, and ``S3DeleteObjectsError`` (S3 failed to delete some objects of a ``delete_objects`` call; it has the ``errors`` and the number deleted so far, ``n_deleted``).
- **Partitions.** S3 ARNs and console URLs support the ``aws-cn`` (China), ``aws-us-gov`` (GovCloud) and ``aws-eusc`` (European Sovereign Cloud) partitions, in addition to ``aws``. Add ``s3pathlib.constants.AwsPartitionEnum``, ``S3Path.get_arn(partition)``, ``S3Path.get_console_url(region=None, partition="aws")`` and ``utils.split_s3_arn``; ``S3Path(arn)``, ``from_s3_arn`` and ``validate_s3_arn`` accept all of them, and ``utils.make_s3_console_url`` takes a ``partition`` (the domains are in ``constants.AWS_CONSOLE_DOMAIN``). ``S3Path.arn`` still returns the ``aws`` ARN. ``validate_s3_uri`` accepts ``s3://bucket`` without the trailing slash. ``s3pathlib.constants`` also has the bucket naming rules (``S3_BUCKET_MIN_LENGTH``, ``S3_BUCKET_MAX_LENGTH``, ``S3_BUCKET_RESERVED_PREFIXES``, ``S3_BUCKET_RESERVED_SUFFIXES``) and ``S3_KEY_MAX_BYTES``.
- **Relative and void paths.** ``S3Path.parents`` supports them like ``pathlib.PurePath.parents`` (the parents of a relative path end with the void path; the void path has none), where it raised ``ValueError``. ``relative_to`` (and ``-``) works between two relative paths. ``is_parent_of`` and ``is_prefix_of`` work between two relative paths (the void path is the parent of every relative path), and give ``False`` for an absolute and a relative path. ``make_relpath`` accepts relative paths as parts and follows the constructor rules. ``S3Path() / x`` gives ``x`` as a relative path, like ``S3Path().joinpath(x)``, and ``S3Path() / [a, b]`` joins the list at once.
- **Deprecations.** Add ``s3pathlib.marker.deprecated``, the standard :pep:`702` decorator: deprecated APIs emit a ``DeprecationWarning`` that points at your line, and type checkers and IDEs flag the call sites. Joining onto a file and using a file as the base of ``relative_to`` are deprecated: ``S3Path("bucket", "folder") / "file.txt"``, ``.joinpath(...)`` and ``S3Path("bucket", "a/b").relative_to(S3Path("bucket", "a"))`` still work but warn, because a file has no sub path; they raise ``S3PathIsNotFolderError`` in 4.0.0. This includes chains such as ``S3Path("bucket") / "folder" / "file.txt"``. Use a dir: ``S3Path("bucket") / "folder/" / "file.txt"``, ``.to_dir()``, or join all parts at once with ``S3Path("bucket").joinpath("folder", "file.txt")`` or ``S3Path("bucket") / ["folder", "file.txt"]``. The misspelled ``quite`` argument of ``sync`` is deprecated for the new ``quiet`` (``quite`` wins when both are given), and the ``ignore_not_found`` argument of ``better_client.delete_object`` never had an effect (S3 never reports a missing key when deleting): both will be removed in 4.0.0.
- **Client.** ``s3_context`` is thread safe (the default client is created at most once, under a lock, and ``attach_s3_client`` replaces it in one step), and creates the default client when first used instead of at import, so importing ``s3pathlib`` has no side effect and environment variables such as ``AWS_PROFILE`` set after the import are honored. An ``S3Path`` produced by a call with an explicit client (``iter_objects(s3_client=...)``, ``head_object(s3_client=...)``) remembers that client and loads its missing metadata with it; other methods use ``s3_client`` or ``s3_context``, however the path was made. Pickle does not keep the client; ``copy`` / ``deepcopy`` do.
- **Writes.** ``write_bytes`` and ``write_text`` accept ``if_match`` and ``if_none_match``, the conditional writes of S3 (``if_none_match="*"`` only writes a new object, ``if_match=<etag>`` only replaces the object if nobody changed it), and so does ``open`` with ``multipart_upload=False``. ``touch`` makes one conditional ``put_object`` call instead of ``head_object`` + ``put_object``, so an object written by someone else in between is never replaced. ``upload_file`` returns a new ``S3Path`` of the uploaded object, like ``write_bytes`` (it returned ``None``). With ``overwrite=False``, the copy methods check the target, then copy conditionally (``IfNoneMatch="*"``), so on AWS an object written in between is not replaced either.
- **Delete and listing.** Add ``better_client.delete_object_all_versions(s3_client, bucket, key)``, which permanently deletes all versions and delete markers of exactly one key. ``S3Path.head_object`` accepts ``version_id``. ``S3Path.list_buckets()`` keeps the region of each bucket in ``response["BucketRegion"]`` (add ``constants.S3_LIST_BUCKETS_MAX_BUCKETS``, 10,000).
- **Sync.** ``sync`` supports S3 compatible endpoints and unsigned clients (``--no-sign-request``), and ``include`` and ``exclude`` accept a list of patterns (all excludes, then all includes).

**Bugfixes**

- ``S3Path.list_buckets()`` failed with ``S3ValidationError`` when the account had a legacy bucket (created in us-east-1 before March 2018, with uppercase letters or underscores). It now lists every bucket S3 returns, and ``from_s3_uri``, ``from_s3_arn`` and ``from_bucket`` accept legacy bucket names.
- ``utils.make_s3_console_url`` did not URL encode the key, so a key with ``&``, ``#``, ``?``, ``+``, ``%`` or spaces opened the wrong object or none at all.
- ``utils.repr_data_size`` showed ``1048575`` bytes as ``1024.00 KB`` instead of ``1.00 MB``, raised ``KeyError`` above 1024 YB, and accepted negative sizes. It now carries rounding over to the next unit, shows larger sizes in YB, and rejects negative sizes with ``ValueError``.
- ``utils.parse_data_size`` raised a bare ``ValueError`` for a number without unit (``"100"``); a bare number now means bytes, and invalid text raises ``ValueError`` with a message.
- ``utils.smart_join_s3_key`` returned ``"/"`` for no parts with ``is_dir=True``; it now returns ``""`` (the bucket root). ``utils.grouper_list`` with ``n < 1`` silently returned everything as one list; it now raises ``ValueError``.
- ``validate_s3_key`` rejected valid keys with non-ASCII characters or characters such as ``~`` and ``%`` (it now accepts any UTF-8 key), and measured the 1024 limit in characters instead of UTF-8 bytes. ``validate_s3_bucket`` rejected valid names such as ``1.2.3`` as IP addresses when Python runs with ``-O``.
- ``S3Path(...)`` ignores empty arguments (``""`` or a void path) when deciding whether the path is a file or a directory. ``S3Path("bucket", "a", S3Path())`` was neither, and ``S3Path("bucket", "a/", "")`` became a file. ``S3Path.make_relpath("a", "/")`` is a dir, like ``S3Path(S3Path(), "a", "/")`` (``make_relpath`` ignored a trailing ``"/"``).
- ``S3Path.change`` failed with a bare ``TypeError`` on a dir, a bucket or the void path, even for ``change()`` or ``change(new_bucket=...)``; it now keeps the last part and the type of the path. ``change(new_bucket=..., new_abspath=...)`` ignored ``new_bucket``, and ``new_abspath`` on a relative path raised ``TypeError``; both work now.
- ``S3Path.is_parent_of`` only detected the direct parent: ``S3Path("bkt/a/").is_parent_of(S3Path("bkt/a/b/c"))`` was ``False``; it now detects every ancestor. ``S3Path.is_prefix_of`` compared the URIs with ``<=`` instead of checking a prefix, so ``S3Path("bkt/b").is_prefix_of(S3Path("bkt/c"))`` was ``True``; it now checks that the key starts with the other key, like the S3 ``Prefix``.
- The ``greater_equal`` and ``less_equal`` filters (``S3Path.size.greater_equal(1000)``) did an ``==`` comparison; they now do ``>=`` and ``<=``.
- A pickled ``S3Path`` carried its cached hash. The hash of a ``str`` differs between Python processes, so after loading it in another process (e.g. with ``multiprocessing``) the path was equal to the same path but had a different hash, and ``dict`` / ``set`` lookups missed it. Pickle (and ``copy``) now saves the path and the metadata but not the caches, and checks the state when loading; protocols 0 and 1 work too.
- ``S3Path.is_delete_marker`` called ``head_object`` when no metadata was loaded. That call can never find a delete marker, and it raised ``S3FileNotExist`` for a missing object and for an object whose latest version is a delete marker, and ``TypeError`` on a relative path. It now only looks at the loaded metadata and never calls AWS.
- The ``ensure_*`` validators showed ``None`` in the error message for a relative path or the void path; they now show the path. ``ensure_relpath`` and ``ensure_not_relpath`` had their error messages swapped.
- The parent of a single part relative path (``S3Path.make_relpath("a").parent``) and ``S3Path(S3Path(), "/")`` are now the void path; they were a "void path that is a dir", for which ``is_void()`` was ``True`` but ``is_relpath()`` was ``False``.
- Comparing an ``S3Path`` with another type (``p == "s3://bucket/key"``, ``p != None``, ``p in ["a", p]``) raised ``AttributeError``. ``==`` now returns ``False`` and ``<`` / ``<=`` / ``>`` / ``>=`` raise ``TypeError``, like ``pathlib``.
- ``S3Path.parts`` returned the internal list, so changing it changed the path but not its cached hash, which broke ``==`` and ``hash``. It returns a copy.
- Sorting ``S3Path`` objects put a dir after the part of its content whose name starts with a character smaller than ``/`` (``-``, ``!``, a space, ...): ``sorted([S3Path("b", "a/"), S3Path("b", "a/-x")])`` gave ``a/-x`` first, while ``pathlib`` and the S3 list APIs put the dir first. A dir now sorts right after the file of the same name and before all of its content. The hash of an ``S3Path`` changed with it, which does not matter as it is never saved.
- When the default boto session could not be created at import time (e.g. ``AWS_PROFILE`` names an unknown profile), the error was silently ignored and every later call failed with ``AttributeError: 'NoneType' object has no attribute 'client'``, even after fixing the environment. The first API call now raises the real error (e.g. ``ProfileNotFound``), and the next call works once the environment is fixed.
- ``better_client.is_bucket_exists`` and ``head_object`` recognized "not found" by looking for ``Not Found`` in the error message, which is not reliable for a ``HEAD`` response; they now check the error code. ``head_object`` with a ``version_id`` that is a delete marker raised ``ClientError`` (S3 answers 405); it now means the object does not exist, so ``is_object_exists(..., version_id=<delete marker>)`` is ``False``. With moto, a missing bucket raised ``NoSuchBucket`` instead of "not found"; both now behave the same.
- ``better_client.paginate_list_objects_v2`` and ``paginate_list_object_versions`` returned more than ``limit`` entries, because ``limit`` only counted the objects / versions and not the folders (common prefixes) and delete markers: ``limit=3`` could return 8 entries. ``limit`` now counts all of them, like ``MaxKeys``, which also applies to ``S3Path.iterdir`` / ``list_object_versions(limit=...)`` and ``delete_object_versions(limit=...)``. A negative ``limit`` is sent to S3, which rejects it (moto ignored it); it now raises ``ValueError``, and ``limit=0`` returns nothing without calling AWS.
- **Data loss**: ``S3Path("bucket", "data/file.txt").delete(is_hard_delete=True)`` permanently deleted all versions of every key starting with ``data/file.txt``, such as ``data/file.txt.bak`` and ``data/file.txt2/...``. It only deletes the versions of ``data/file.txt``. ``delete(version_id=v, is_hard_delete=True)`` ignored ``version_id`` and deleted every version of the file (it now raises ``ValueError``, see above).
- ``better_client.delete_dir`` and ``delete_object_versions`` ignored the objects S3 failed to delete (``delete_objects`` answers HTTP 200 and lists them in ``Errors``) and counted them as deleted. They now raise ``S3DeleteObjectsError`` and stop.
- ``S3Path.list_object_versions()`` yielded the entries of the earlier pages again after each page: 8 versions listed with ``batch_size=2`` gave 20 entries. Each entry is now yielded once, in the S3 order (by key, then newest first). On a file it also listed the versions of every key starting with ``file.txt`` (``file.txt.bak``); it now lists this exact key only. Invalid ``limit`` / ``batch_size`` raise ``ValueError`` when the method is called, and ``limit=None`` means no limit, as when it is left out (``TypeError`` before; also for ``iter_objects``, ``iterdir`` and the ``better_client`` pagination functions). On a relative path or the void path it raised a bare ``TypeError`` from botocore; it now raises ``S3PathTypeError``.
- ``S3Path.list_object_versions()`` could list a delete marker after the version it hides when both were written in the same second (S3 timestamps have a one second resolution), so the first entry was not the latest one: e.g. ``p.list_object_versions().one()`` after ``p.write_bytes(...)`` then ``p.delete()``. The entry that S3 marks as the latest (``IsLatest``) now always comes first.
- ``S3Path.put_bucket_versioning(enable_mfa_delete=...)`` always failed with ``ParamValidationError`` (it sent ``MFADelete`` as a bool) and replaced ``Status`` (``enable_mfa_delete=True`` enabled versioning even with ``enable_versioning=False``). It now sends ``"Enabled"`` / ``"Disabled"`` and keeps ``Status``; ``enable_mfa_delete=None`` (default) does not send ``MFADelete``.
- ``S3Path.create_bucket()`` without ``region`` always asked for ``us-east-1``, which S3 rejects with ``IllegalLocationConstraintException`` when the client is in another region. ``region`` now defaults to ``None``, the region of the S3 client. ``S3Path.list_buckets()`` made one ListBuckets request without ``MaxBuckets``, which S3 rejects for an account allowed more than 10,000 buckets; it now fetches every page.
- ``S3Path("bucket", "folder/").exists()`` raised ``NoSuchBucket`` when the bucket did not exist, while a file in a missing bucket returned ``False``; a folder in a missing bucket now does not exist either. ``exists()`` on a path without bucket raised a different error for each kind of path (a bare ``TypeError`` for the void path, a botocore ``TypeError`` for a relative file, ``S3PathTypeError`` for a relative folder); it always raises ``S3PathTypeError`` before calling AWS. Reading a metadata property of a bucket, a relative path or the void path raised a botocore error; it raises ``S3PathTypeError`` too (a bucket from ``list_buckets()`` keeps its ``last_modified_at``).
- An ``S3Path`` returned by ``list_object_versions()`` (or by ``write_bytes()`` with versioning) loaded its missing metadata from the latest version, so an old version silently got the size, user metadata and version id of the latest one. It now loads them from its own version. The ``version_id`` of a path returned by ``iter_objects()`` / ``iterdir()`` was always ``"null"`` because the list API does not return it; it now loads the real one.
- ``read_bytes(range=...)``, ``read_bytes(part_number=...)`` and ``read_bytes(response_*=...)`` stored the response as the metadata of the object, so ``size`` became the length of the range and ``content_type`` the overridden header. They no longer fill the metadata.
- The delete marker returned by ``S3Path.delete()`` with versioning had ``is_delete_marker()`` ``False``, and reading its ``size`` raised ``S3FileNotExist``; it is now a delete marker (``is_delete_marker()`` is ``True``). ``S3Path("bucket", "folder/").delete()`` ignored ``check_sum_algorithm`` (it was only used with ``is_hard_delete=True``). ``delete`` on a relative path raised a botocore ``TypeError`` and on the void path a bare ``ValueError``; both raise ``S3PathTypeError`` before calling AWS.
- ``request_payer`` and the bucket owners were not sent with every call: the listing of the source folder and the check of ``overwrite=False`` of the copy methods, and the listing of the versions of ``delete(is_hard_delete=True)``, which a requester-pays bucket refuses. They are now sent with every call; the calls on the source bucket get ``expected_source_bucket_owner``, the ones on the target bucket ``expected_bucket_owner``. ``better_client.is_object_exists`` and ``paginate_list_object_versions`` have the matching arguments.
- ``S3Path.sync(..., bsm=s3_client)`` always failed, because it called ``bsm.awscli()``, which only a ``BotoSesManager`` has. ``sync`` raises ``FileNotFoundError`` with a message telling to install the AWS CLI when the ``aws`` command is not found, and ``ValueError`` with a message when neither path is in S3.

**Minor Improvements**

- Support ``smart_open`` 8.x. ``S3Path.create_bucket`` is no longer beta and no longer warns.
- Encode spaces in object tags as ``%20`` instead of ``+`` when sending the ``Tagging`` parameter, like the official AWS SDKs, so S3 cannot read them as a literal plus sign. ``S3Path.put_tags`` returns a copy of the given tags.
- The ``UserWarning`` for a user metadata key with upper case letters says which lowercase key S3 stores, points at the line of your code (not a line inside ``s3pathlib``), and is now also emitted by the copy methods (``write_bytes``, ``write_text``, ``touch`` and ``open`` already did).
- Clearer errors, all still the builtin exception they were: ``S3Path(...)``, ``joinpath``, ``/`` and ``make_relpath`` raise ``TypeError`` naming the wrong argument type; ``ensure_not_object`` / ``ensure_not_file`` / ``ensure_not_dir`` / ``ensure_not_relpath`` / ``abspath`` / ``dirpath`` / ``root`` raise ``S3PathTypeError`` naming the path; ``ensure_relpath`` raises ``S3PathIsNotRelpathError``; ``is_parent_of`` raises ``S3PathIsNotFolderError`` on a file; ``relative_to`` raises ``TypeError`` for an argument that is not an ``S3Path`` (it was ``AttributeError``) and its ``ValueError`` says why the path is not under the other one; ``get_arn``, ``get_console_url`` and ``make_s3_console_url`` raise ``S3ValidationError`` for an unsupported partition (listing the supported ones) or an empty region; ``ensure_not_exists`` raises ``S3FileAlreadyExist``, ``S3FolderAlreadyExist`` or ``S3BucketAlreadyExist`` depending on the path, instead of ``S3AlreadyExist`` saying "s3 object" for every path.
- ``repr`` of an ``S3Path`` with a bucket escapes quotes in the key like a relative path does (``S3Path("s3://b/it's.txt")``). Deleting a filterable property (``del p.key``) raises ``AttributeError`` with a clear message. ``validate_s3_bucket`` lists the invalid characters in sorted order. ``s3_context.attach_s3_client(None)`` raises ``TypeError`` (any other object is accepted, e.g. a stub in tests). ``S3FileNotExist`` from ``better_client.head_object`` names the version and keeps the ``ClientError`` as ``__cause__``. ``s3pathlib.tag.parse_tags`` no longer checks its argument.
- Rewrite the docstrings of the whole library, which are now the reference of the behavior: the six states of a path (``s3pathlib.core.base``), what each kind of path returns for ``bucket`` / ``key`` / ``uri`` / ``arn`` / ``console_url``, how paths compare (equality ignores the object version; the order is part by part like ``pathlib``), every filter of ``FilterableProperty``, the metadata snapshot (``s3pathlib.core.metadata``), and for each group of methods (bucket, ``exists``, read / write, ``open``, upload, copy, delete, tagging, listing, ``sync``) every argument, which boto3 errors are raised as is, what is atomic and what is not. Docstring examples were fixed (wrong values, swapped operands, a non-existent ``path`` argument of ``upload_dir``) and are run as tests.
- Document the ``better_client`` functions the same way: results of the pagination functions are lazy, can be iterated once, and raise when the iteration starts; ``prefix`` is a string prefix, not a folder; the truth table of ``is_content_an_object``; ``update_bucket_tagging`` and ``update_object_tagging`` merge like ``dict.update`` and are not atomic; ``upload_dir`` builds the keys, the ``prefix`` rules and the errors; deleting a missing key in a versioned bucket adds a delete marker. ``better_client.list_object_versions.CommonPrefixTypeDefIterproxy`` is now the same class as in ``better_client.list_objects``. Fix the ``expire_at`` docs: it is the ``Expires`` HTTP header, not the expiration date of a lifecycle rule.

**Miscellaneous**

- Package and tooling: switch the build backend from poetry to setuptools, manage the environment with mise and uv, use the SPDX license expression ``Apache-2.0`` and add the Python version classifiers, regenerate ``requirements*.txt`` with ``mise run export`` and remove the stale ones, remove the old ``.readthedocs.yaml`` that competed with ``.readthedocs.yml``, configure ruff in ``pyproject.toml``, add ``s3pathlib.paths`` for project paths, and add the ``typing-extensions`` dependency on Python < 3.13 for the ``deprecated`` backport.
- Arguments passed on to boto3 default to the private ``s3pathlib._arg.OPT`` ("not given"), replacing ``func-args``. ``None`` is not "not given": botocore rejects it with ``ParamValidationError`` (S3 has no ``None`` value), so a condition such as ``if_match=p.etag`` is never silently dropped. ``s3pathlib.type.PathType`` is ``str | os.PathLike``; the library uses the standard library ``pathlib`` (a ``pathlib_mate.Path`` is still accepted).
- Tests: every test module that calls AWS uses the new ``s3pathlib.tests.mock_aws.BaseTest`` (the old ``s3pathlib.tests.mock`` with ``cls.bsm`` is removed) and runs against moto (``TestMock``) and, with ``S3PATHLIB_TEST_REAL_AWS=true`` (``mise run cov-aws``), against real AWS (``TestRealAws``); ``@mock_only`` / ``@real_aws_only`` mark tests that only work in one mode, and each test gets its own S3 folder. The ``sync`` tests run ``aws s3 sync`` end to end against a moto server (``flask`` and ``flask-cors`` are test dependencies) or AWS when the AWS CLI is installed. Shared helpers are in ``s3pathlib.tests.aws_helpers``. Unused test data was removed.
- The mise tasks ``setup-aws-ci`` and ``teardown-aws-ci`` (idempotent) create / delete the test buckets, a lifecycle rule that expires the test objects after one day, the test IAM user (its policy is built in code, replacing ``.github/workflows/iam-policy.json``, with full access to the temporary ``s3pathlib-test-tmp-*`` buckets) and its GitHub Actions secrets; the AWS profiles are defined in ``mise.toml``.
- GitHub Actions CI is rewritten with uv: on every push to ``main`` and ``dev``, Python 3.11 to 3.14 on both Ubuntu and Windows, running the whole suite against moto and real AWS; each run uses its own S3 folder (``GITHUB_RUN_ID``), so concurrent runs do not interfere.
- The documentation notebooks use the standard library ``pathlib`` instead of ``pathlib_mate``.


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
