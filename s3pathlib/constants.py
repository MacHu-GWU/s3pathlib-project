# -*- coding: utf-8 -*-

import enum

IS_DELETE_MARKER = "IsDeleteMarker"

# The maximum length of an S3 object key, in UTF-8 encoded bytes.
S3_KEY_MAX_BYTES = 1024


class AwsPartitionEnum(enum.StrEnum):
    """
    AWS partitions supported in S3 ARNs, e.g. ``arn:aws-cn:s3:::my-bucket``.
    """

    aws = "aws"
    aws_cn = "aws-cn"
    aws_us_gov = "aws-us-gov"
