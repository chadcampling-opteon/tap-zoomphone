"""Stream type classes for tap-zoomphone."""

from __future__ import annotations

import sys
import typing as t
from importlib import resources

if sys.version_info < (3, 12):
    from typing_extensions import override
else:
    from typing import override  # noqa: ICN003

from dateutil.relativedelta import relativedelta

from tap_zoomphone.client import ZoomPhoneStream


SCHEMAS_DIR = resources.files(__package__) / "schemas"


class UsersStream(ZoomPhoneStream):
    """Define custom stream."""

    name = "users"
    path = "/users"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = None
    records_jsonpath = "$.users[*]"
    
    schema_filepath = SCHEMAS_DIR / "zoom_phone_users_schema.json"  # noqa: ERA001

class SmsSessionsStream(ZoomPhoneStream):
    """Define custom stream."""

    name = "sms_sessions"
    path = "/sms/sessions"
    primary_keys: t.ClassVar[list[str]] = ["session_id"]
    replication_key = "last_access_time"
    records_jsonpath = "$.sms_sessions[*]"
    schema_filepath = SCHEMAS_DIR / "zoom_phone_sms_sessions_schema.json"  # noqa: ERA001
    
    _history_window = relativedelta(months=6)
    
class CallHistoryStream(ZoomPhoneStream):
    """Define custom stream."""

    name = "call_history"
    path = "/call_history"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = "start_time"
    records_jsonpath = "$.call_logs[*]"
    schema_filepath = SCHEMAS_DIR / "zoom_phone_call_history_schema.json"  # noqa: ERA001
    
    _page_size = 300
    _history_window = relativedelta(months=6)
    
    def get_child_context(self, record, context):
        return { "id": record["id"]}
    
class CallHistoryPathStream(ZoomPhoneStream):
    """Define custom stream."""

    name = "call_history_path"
    path = "/call_history"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    records_jsonpath = "$"
    schema_filepath = SCHEMAS_DIR / "zoom_phone_call_history_path_schema.json"  # noqa: ERA001
    parent_stream_type = CallHistoryStream
    ignore_parent_replication_key = False
    
    state_partitioning_keys = []
    _page_size = None
    _LOG_REQUEST_METRICS = False

    
    def get_url(self, context):
        url = super().get_url(context)
        id = context["id"]
        return  f"{url}/{id}"

    def _log_metric(self, point):
        pass
    
    def _write_request_duration_log(self, endpoint, response, context, extra_tags):
        pass
    
    def post_process(self, row, context = None):
        """Zoom API has been returning items outside schema with training spaces"""
        
        result_reason = row.get('result_reason')
        row['result_reason'] = result_reason.strip() if result_reason else None
        return row
