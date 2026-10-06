# -*- coding: utf-8 -*-

"""
Mark public API as deprecated.

Use the standard :pep:`702` ``@deprecated`` decorator. At runtime it emits a
``DeprecationWarning`` that points at the caller's line; type checkers and
IDEs also flag every call site (e.g. strike-through), so both humans and AI
coding assistants notice before running the code.

Apply it directly on the function, class or method. Do not wrap it in a helper
function, otherwise type checkers no longer recognize it. Write the message
as::

    Deprecated since {version}, will be removed in {version}. Use {replacement} instead.

Example::

    from s3pathlib.marker import deprecated

    class S3Path:
        @deprecated(
            "Deprecated since 3.1.0, will be removed in 4.0.0. "
            "Use S3Path.new_method instead."
        )
        def old_method(self): ...
"""

import sys

if sys.version_info >= (3, 13):  # pragma: no cover
    from warnings import deprecated
else:  # pragma: no cover
    from typing_extensions import deprecated

__all__ = [
    "deprecated",
]
