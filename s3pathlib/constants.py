# -*- coding: utf-8 -*-

import enum

IS_DELETE_MARKER = "IsDeleteMarker"

# The maximum length of an S3 object key, in UTF-8 encoded bytes.
S3_KEY_MAX_BYTES = 1024

# Naming rules for a new general purpose bucket.
# Ref: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
S3_BUCKET_MIN_LENGTH = 3
S3_BUCKET_MAX_LENGTH = 63
S3_BUCKET_RESERVED_PREFIXES = (
    "xn--",
    "sthree-",
    "amzn-s3-demo-",
)
S3_BUCKET_RESERVED_SUFFIXES = (
    "-s3alias",  # access point alias
    "--ol-s3",  # Object Lambda access point alias
    ".mrap",  # Multi-Region Access Point
    "--x-s3",  # directory bucket
    "--table-s3",  # S3 Tables bucket
)


class AwsPartitionEnum(enum.StrEnum):
    """
    AWS partitions supported in S3 ARNs, e.g. ``arn:aws-cn:s3:::my-bucket``.
    """

    aws = "aws"
    aws_cn = "aws-cn"
    aws_us_gov = "aws-us-gov"
    aws_eusc = "aws-eusc"  # AWS European Sovereign Cloud


# AWS Management Console domain of each partition. A regional console prepends
# the region, e.g. ``us-east-1.console.aws.amazon.com``. Note that the console
# domain is not the API endpoint suffix (e.g. ``amazonaws.com.cn``).
AWS_CONSOLE_DOMAIN = {
    AwsPartitionEnum.aws: "console.aws.amazon.com",
    AwsPartitionEnum.aws_cn: "console.amazonaws.cn",
    AwsPartitionEnum.aws_us_gov: "console.amazonaws-us-gov.com",
    AwsPartitionEnum.aws_eusc: "console.amazonaws-eusc.eu",
}
