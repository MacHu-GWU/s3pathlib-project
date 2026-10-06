# -*- coding: utf-8 -*-

"""
Common content types for S3 objects.
"""

from __future__ import annotations

class ContentTypeEnum:
    """
    Common content types that browsers can render. Set one of them as the
    object's content type, and the "Open" button in the AWS S3 console
    previews the object in the browser instead of downloading it.

    Example::

        >>> S3Path("bucket", "data.json").write_text(
        ...     "{}", content_type=ContentTypeEnum.app_json
        ... )
    """
    image_jpeg = "image/jpeg"
    image_png = "image/png"
    image_gif = "image/gif"
    image_bmp = "image/bmp"
    image_tiff = "image/tiff"
    image_svg_xml = "image/svg+xml"
    html = "text/html"
    text_plain = "text/plain"
    text_rtf = "text/rtf"
    app_pdf = "application/pdf"
    app_json = "application/json"
    app_zip = "application/zip"
    app_gzip = "application/x-gzip"
    app_ms_word = "application/msword"
    audio_mpeg = "audio/mpeg"
