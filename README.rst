.. image:: https://readthedocs.org/projects/s3pathlib/badge/?version=latest
    :target: https://s3pathlib.readthedocs.io/en/latest/
    :alt: Documentation Status

.. image:: https://github.com/MacHu-GWU/s3pathlib-project/actions/workflows/main.yml/badge.svg
    :target: https://github.com/MacHu-GWU/s3pathlib-project/actions?query=workflow:CI

.. image:: https://codecov.io/gh/MacHu-GWU/s3pathlib-project/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/MacHu-GWU/s3pathlib-project

.. image:: https://img.shields.io/pypi/v/s3pathlib.svg
    :target: https://pypi.org/project/s3pathlib/

.. image:: https://img.shields.io/pypi/l/s3pathlib.svg
    :target: https://pypi.org/project/s3pathlib/

.. image:: https://img.shields.io/pypi/pyversions/s3pathlib.svg
    :target: https://pypi.org/project/s3pathlib/

.. image:: https://img.shields.io/pypi/dm/s3pathlib.svg
    :target: https://pypi.org/project/s3pathlib/

.. image:: https://img.shields.io/badge/✍️_Release_History!--None.svg?style=social&logo=github
    :target: https://github.com/MacHu-GWU/s3pathlib-project/blob/main/release-history.rst

.. image:: https://img.shields.io/badge/⭐_Star_me_on_GitHub!--None.svg?style=social&logo=github
    :target: https://github.com/MacHu-GWU/s3pathlib-project

------

.. image:: https://img.shields.io/badge/Link-API-blue.svg
    :target: https://s3pathlib.readthedocs.io/en/latest/py-modindex.html

.. image:: https://img.shields.io/badge/Link-Source_Code-blue.svg
    :target: https://s3pathlib.readthedocs.io/en/latest/py-modindex.html

.. image:: https://img.shields.io/badge/Link-Submit_Issue-blue.svg
    :target: https://github.com/MacHu-GWU/s3pathlib-project/issues

.. image:: https://img.shields.io/badge/Link-Request_Feature-blue.svg
    :target: https://github.com/MacHu-GWU/s3pathlib-project/issues

.. image:: https://img.shields.io/badge/Link-Download-blue.svg
    :target: https://pypi.org/project/s3pathlib/


Welcome to ``s3pathlib`` Documentation
==============================================================================
`s3pathlib <https://s3pathlib.readthedocs.io/en/latest/>`_ is a Python SDK on top of `boto3 <https://docs.aws.amazon.com/boto3/latest/>`_ that works with Amazon S3 the way the standard library `pathlib <https://docs.python.org/3/library/pathlib.html>`_ works with local files: build paths, read and write objects, list and filter folders, copy, move and delete them, with or without versioning.

The full guide and the API reference are on `Read the Docs <https://s3pathlib.readthedocs.io/en/latest/>`_.


Install
------------------------------------------------------------------------------
``s3pathlib`` is released on PyPI and needs Python 3.11 or newer:

.. code-block:: console

    $ pip install s3pathlib


Quick Look
------------------------------------------------------------------------------
Build paths. This part never calls AWS:

.. code-block:: python

    from s3pathlib.api import S3Path

    p = S3Path("bucket", "folder", "file.txt")  # also S3Path("s3://bucket/folder/file.txt")
    p.uri          # 's3://bucket/folder/file.txt'
    p.key          # 'folder/file.txt'
    p.parent       # S3Path('s3://bucket/folder/')
    p.arn          # 'arn:aws:s3:::bucket/folder/file.txt'
    p.console_url  # 'https://console.aws.amazon.com/s3/object/bucket?prefix=folder/file.txt'

Talk to S3. ``s3pathlib`` uses the default boto3 client unless you attach your own:

.. code-block:: python

    import boto3
    from s3pathlib.api import s3_context

    s3_context.attach_s3_client(boto3.Session(profile_name="my_profile").client("s3"))

    p = S3Path("bucket", "folder", "file.txt")
    p.write_text("hello")       # returns a new S3Path of the written object
    p.read_text()               # 'hello'
    p.size                      # 5

    folder = S3Path("bucket", "folder/")    # a trailing "/" makes it a folder
    for csv in folder.iter_objects().filter(S3Path.size >= 1_000_000).filter_by_ext(".csv"):
        print(csv.uri)
    folder.copy_dir(S3Path("bucket", "backup/"), overwrite=True)
    folder.delete()             # every object under the folder

``S3Path.open`` gives a file object, so it works with ``json``, ``csv``, ``pandas`` and any other library that reads or writes files:

.. code-block:: python

    import json

    with S3Path("bucket", "config.json").open("w") as f:
        json.dump({"name": "alice"}, f)


Using s3pathlib with an AI Coding Agent
------------------------------------------------------------------------------
The `pypi-s3pathlib <https://github.com/MacHu-GWU/s3pathlib-project/tree/main/.claude/skills/pypi-s3pathlib>`_ folder is a self-contained `Claude Code skill <https://code.claude.com/docs/en/skills>`_ that teaches an AI agent the public API of s3pathlib 3.x. Copy it into the ``.claude/skills/`` folder of your project, and the agent loads it whenever it works with s3pathlib, so it writes code with the current API instead of guessing from older versions.


Upgrading from 2.x
------------------------------------------------------------------------------
3.0.0 is a breaking release; import everything from ``s3pathlib.api``. See the `release history <https://github.com/MacHu-GWU/s3pathlib-project/blob/main/release-history.rst>`_ and the "Upgrade from 2.x" chapter of the `guide <https://s3pathlib.readthedocs.io/en/latest/#comprehensive-guide>`_.

If you use `Claude Code <https://code.claude.com/>`_, copy the `s3pathlib-upgrade-to-3 <https://github.com/MacHu-GWU/s3pathlib-project/tree/main/.claude/skills/s3pathlib-upgrade-to-3>`_ folder into the ``.claude/skills/`` folder of your project and run ``/s3pathlib-upgrade-to-3``: it scans your code and notebooks for 2.x usage, rewrites the renames, and walks you through the behavior changes.


Getting Help
------------------------------------------------------------------------------
Ask a question or report a bug on `GitHub Issues <https://github.com/MacHu-GWU/s3pathlib-project/issues/new/choose>`_.


Contributing
------------------------------------------------------------------------------
Please see the `Contribution Guidelines <https://github.com/MacHu-GWU/s3pathlib-project/blob/main/CONTRIBUTING.rst>`_.


Copyright
------------------------------------------------------------------------------
s3pathlib is an open source project. See the `LICENSE <https://github.com/MacHu-GWU/s3pathlib-project/blob/main/LICENSE>`_ file for more information.
