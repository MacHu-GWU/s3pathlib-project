# -*- coding: utf-8 -*-

"""
Provide compatibility with older versions of Python and dependent libraries.
"""

try:
    import smart_open
except ImportError:
    smart_open = None
