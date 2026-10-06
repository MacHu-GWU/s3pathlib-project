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
- Remove ``s3pathlib.exc.ensure_one_and_only_one_not_none``, it was not used by the library.
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
- ``utils.make_s3_console_url`` and ``utils.make_s3_select_console_url`` accept a ``partition`` argument and support the China (``console.amazonaws.cn``) and European Sovereign Cloud (``console.amazonaws-eusc.eu``) consoles. The console domains are in ``s3pathlib.constants.AWS_CONSOLE_DOMAIN``. ``is_us_gov_cloud=True`` still works and means ``partition="aws-us-gov"``.
- Add ``s3pathlib.marker.deprecated``, the standard :pep:`702` decorator. Deprecated APIs now emit a ``DeprecationWarning`` that points at the caller, and type checkers / IDEs flag the call sites.

**Bugfixes**

- ``S3Path.list_buckets()`` failed with ``S3ValidationError`` when the account had a legacy bucket (created in us-east-1 before March 2018, with uppercase letters or underscores). It now lists every bucket S3 returns. ``S3Path.from_s3_uri``, ``S3Path.from_s3_arn`` and ``S3Path.from_bucket`` also accept legacy bucket names.
- ``utils.make_s3_console_url`` and ``utils.make_s3_select_console_url`` did not URL encode the key, so a key with ``&``, ``#``, ``?``, ``+``, ``%`` or spaces opened the wrong object or none at all.
- ``utils.repr_data_size`` showed ``1048575`` bytes as ``1024.00 KB`` instead of ``1.00 MB``, raised ``KeyError`` above 1024 YB, and accepted negative sizes. It now carries rounding over to the next unit, shows larger sizes in YB, and rejects negative sizes with ``ValueError``.
- ``utils.parse_data_size`` raised a bare ``ValueError`` for a number without unit (e.g. ``"100"``); a bare number now means bytes, and invalid text raises ``ValueError`` with a message.
- ``utils.smart_join_s3_key`` returned ``"/"`` for no parts with ``is_dir=True``; it now returns ``""`` (the bucket root).
- ``utils.grouper_list`` with ``n < 1`` silently returned everything as one list; it now raises ``ValueError``.
- ``validate_s3_key`` rejected valid keys with non-ASCII characters or characters such as ``~`` and ``%``. It now accepts any UTF-8 key.
- ``validate_s3_key`` measured the 1024 limit in characters; it now measures UTF-8 bytes, as S3 does.
- ``validate_s3_bucket`` rejected valid names such as ``1.2.3`` as IP addresses when Python runs with ``-O``.
- ``S3Path(...)`` ignores empty arguments (``""`` or a void path) when deciding whether the path is a file or a directory. Before, ``S3Path("bucket", "a", S3Path())`` was neither a file nor a directory, and ``S3Path("bucket", "a/", "")`` became a file.
- ``S3Path.parts`` returned the internal list, so changing it changed the path but not its cached hash, which broke ``==`` and ``hash``. It now returns a copy.

**Minor Improvements**

- Support ``smart_open`` 8.x.
- Support ``boto_session_manager`` 2.x, which moved ``BotoSesManager`` to ``boto_session_manager.api``.
- ``S3Path.create_bucket`` is no longer beta and no longer emits a warning.
- Encode spaces in object tags as ``%20`` instead of ``+`` when sending the ``Tagging`` parameter, the same as the official AWS SDKs, so S3 cannot read them as a literal plus sign.
- ``S3Path(...)`` raises ``TypeError`` with a message naming the wrong argument type, instead of a bare ``TypeError``.

**Miscellaneous**

- Add the ``typing-extensions`` dependency on Python < 3.13, for the ``deprecated`` backport.
- ``utils.ensure_s3_object`` and ``utils.ensure_s3_dir`` raise ``S3ValidationError`` (still a ``ValueError``).
- Fix package metadata: use the SPDX license expression ``Apache-2.0`` and correct the ``classifiers`` field name.
- Switch the build backend from poetry to setuptools, and manage the development environment with mise and uv.
- Add ``s3pathlib.paths`` to centralize project paths, and simplify the test helpers in ``s3pathlib.tests``.
- Disable unit tests that run against real AWS; only the moto-mocked tests run by default.


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
