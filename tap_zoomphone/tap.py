"""ZoomPhone tap class."""

from __future__ import annotations

from singer_sdk import Tap
from singer_sdk import typing as th  # JSON schema typing helpers

from tap_zoomphone import streams


class TapZoomPhone(Tap):
    """ZoomPhone tap class."""

    name = "tap-zoomphone"

    
    config_jsonschema = th.PropertiesList(
        th.Property(
            "client_id",
            th.StringType,
            required=True,
            secret=False, 
            title="oAuth Client ID",
            description="The Client ID for the account_credentials oAuth flow",
        ),
        th.Property(
            "client_secret",
            th.StringType,
            required=True,
            secret=True,  # Flag config as protected.
            title="oAuth Client Secret",
            description="The Client Secret for the account_credentials oAuth flow",
        ),
        th.Property(
            "account_id",
            th.StringType,
            required=True,
            title="Zoom Account ID",
            description="Required for auth token creation",
        ),
        th.Property(
            "start_date",
            th.DateTimeType,
            description="The earliest record date to sync",
        ),
    ).to_dict()

    def discover_streams(self) -> list[streams.ZoomPhoneStream]:
        """Return a list of discovered streams.

        Returns:
            A list of discovered streams.
        """
        return [
            streams.UsersStream(self),
            streams.SmsSessionsStream(self),
            streams.CallHistoryStream(self),
            streams.CallHistoryPathStream(self),
        ]


if __name__ == "__main__":
    TapZoomPhone.cli()
