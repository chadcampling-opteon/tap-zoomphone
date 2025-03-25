"""Tests standard tap features using the built-in SDK tests library."""

import datetime
from dateutil.relativedelta import relativedelta

from singer_sdk.testing import get_tap_test_class, SuiteConfig

from tap_zoomphone.tap import TapZoomPhone

SAMPLE_CONFIG = {
    "start_date": (datetime.datetime.now(datetime.timezone.utc) - relativedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
}

TEST_SUITE_CONFIG = SuiteConfig(
)

# Run standard built-in tap tests from the SDK:
TestTapZoomPhone = get_tap_test_class(
    tap_class=TapZoomPhone,
    config=SAMPLE_CONFIG,
    suite_config=TEST_SUITE_CONFIG
)


