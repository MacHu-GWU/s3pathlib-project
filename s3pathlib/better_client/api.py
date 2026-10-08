# -*- coding: utf-8 -*-

from .head_bucket import is_bucket_exists
from .head_object import head_object
from .head_object import is_object_exists
from .tagging import update_bucket_tagging
from .tagging import update_object_tagging
from .upload import upload_dir
from .list_objects import ObjectTypeDefIterproxy
from .list_objects import CommonPrefixTypeDefIterproxy
from .list_objects import ListObjectsV2OutputTypeDefIterproxy
from .list_objects import paginate_list_objects_v2
from .list_objects import is_content_an_object
from .list_objects import calculate_total_size
from .list_objects import count_objects
from .list_object_versions import ObjectVersionTypeDefIterproxy
from .list_object_versions import DeleteMarkerEntryTypeDefIterproxy
from .list_object_versions import ListObjectVersionsOutputTypeDefIterproxy
from .list_object_versions import paginate_list_object_versions
from .delete_object import delete_object
from .delete_object import delete_dir
from .delete_object import delete_object_versions
from .delete_object import delete_object_all_versions
