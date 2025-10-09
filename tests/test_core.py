"""Tests standard tap features using the built-in SDK tests library."""

import datetime
from dateutil.relativedelta import relativedelta

from singer_sdk.testing import get_tap_test_class, SuiteConfig

from tap_zoomphone.tap import TapZoomPhone

DYNAMIC_START_DATE = (datetime.datetime.now(datetime.timezone.utc) - relativedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

SAMPLE_CONFIG = {
    "start_date": DYNAMIC_START_DATE,
}

TEST_SUITE_CONFIG = SuiteConfig(
)

SAMPLE_STATE = {
     "bookmarks": {
        "call_history": {
            "replication_key": "start_time",
            "replication_key_value": DYNAMIC_START_DATE
        },
        "sms_sessions": {
            "replication_key": "last_access_time",
            "replication_key_value": DYNAMIC_START_DATE
        },
        "call_history_path": {}
    }
}

# Run standard built-in tap tests from the SDK:
TestTapZoomPhone = get_tap_test_class(
    tap_class=TapZoomPhone,
    config=SAMPLE_CONFIG,
    suite_config=TEST_SUITE_CONFIG,
    state=SAMPLE_STATE
)


