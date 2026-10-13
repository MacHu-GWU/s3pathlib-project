# -*- coding: utf-8 -*-

"""
Code written for s3pathlib 2.x, used by ``test_scan.py``. It is parsed, never
run. Each rule of ``scan.py`` is hit at least once; the comment at the end of a
line names the rule it hits.
"""

import boto3
import s3pathlib
import s3pathlib.compat  # M12
from s3pathlib import S3Path  # M01
from s3pathlib import context  # M02
from s3pathlib.aws import Context  # M03
from s3pathlib.api import is_bucket_exists  # M13
from s3pathlib.utils import md5_binary  # M10
from s3pathlib.marker import deprecate_v1  # M11
from s3pathlib.exc import _S3PathTypeError  # M14
from s3pathlib.validate import S3BucketValidationError  # M18
from s3pathlib.tests.mock import BaseTest  # M16
from func_args import NOTHING  # M17
from s3pathlib import utils
from s3pathlib import validate
from s3pathlib import api

boto_ses = boto3.Session()
context.attach_boto_session(boto_ses)  # M02
print(context.aws_account_id)  # M02
s3_client = s3pathlib.context.s3_client  # M02

p = S3Path("bucket", "folder", "file.txt")
p.read_text(bsm=s3_client)  # M04
p.delete(check_sum_algorithm="CRC32")  # M05
S3Path.sync("/tmp/data", S3Path("bucket", "data/"), quite=True)  # M06, S10
print(p.get_regional_console_url("us-east-1"))  # M07
print(p.us_gov_cloud_console_url)  # M07
url = utils.make_s3_console_url("bucket", "key", is_us_gov_cloud=True)  # M07
p.delete_if_exists()  # M08
result = api.paginate_list_objects_v2(s3_client, "bucket", "prefix/")  # M13
for dct in result.common_prefixs():  # M09
    print(dct)
digest = utils.md5_binary(b"data")  # M10
charset = validate.valid_bucket_charset  # M18
with p.open("r", ignore_ext=True) as f:  # M15
    print(f.read())
p.update_metadata({"a": "b"})  # M19


class Test(BaseTest):
    def test_something(self):
        print(self.bsm)  # S11


res = p.copy_file(S3Path("bucket", "copy.txt"))  # S01
print(res["CopyObjectResult"])
for child in S3Path("bucket", "folder/").iterdir():  # S02
    print(child)
p.delete(version_id="v1", is_hard_delete=True)  # S03
_ = p.delete()

try:
    p.copy_file(S3Path("bucket", "copy.txt"))
except botocore.exceptions.ClientError:  # S04
    pass

for csv in S3Path("bucket", "folder/").iter_objects().filter_by_ext("csv"):  # S05
    print(csv)
with p.open("r", range="bytes=0-9") as f:  # S06
    print(f.read())
with p.open("w", if_none_match="*") as f:  # S07
    f.write("x")
p.metadata["owner"] = "alice"  # S08
api.delete_object_versions(s3_client, "bucket", prefix="data/file.txt")  # M13, S09

new = S3Path("bucket") / "folder" / "file.txt"  # D01
s3dir = S3Path("bucket", "data/")
new = s3dir / "folder" / "file.txt"  # D01
new = S3Path("bucket", "folder").joinpath("file.txt")  # D01
rel = new.relative_to(S3Path("bucket", "folder"))  # D02
