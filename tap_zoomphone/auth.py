"""ZoomPhone Authentication."""

from __future__ import annotations

from singer_sdk.authenticators import OAuthAuthenticator, SingletonMeta


# The SingletonMeta metaclass makes your streams reuse the same authenticator instance.
# If this behaviour interferes with your use-case, you can remove the metaclass.
class ZoomPhoneAuthenticator(OAuthAuthenticator, metaclass=SingletonMeta):
    """Authenticator class for ZoomPhone."""

    @property
    def oauth_request_body(self) -> dict:
        """Define the OAuth request body for the AutomaticTestTap API.

        Returns:
            A dict with the request body
        """
        return {
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "account_id": self.config["account_id"],
            "grant_type": "account_credentials",
        }

    @classmethod
    def create_for_stream(cls, stream) -> ZoomPhoneAuthenticator:  # noqa: ANN001
        """Instantiate an authenticator for a specific Singer stream.

        Args:
            stream: The Singer stream instance.

        Returns:
            A new authenticator.
        """
        return cls(
            stream=stream,
            auth_endpoint="https://zoom.us/oauth/token",
            oauth_scopes="",
        )
