"""ZoomPhone Authentication."""


import sys

from singer_sdk.authenticators import OAuthAuthenticator, SingletonMeta

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


# The SingletonMeta metaclass makes your streams reuse the same authenticator instance.
# If this behaviour interferes with your use-case, you can remove the metaclass.
class ZoomPhoneAuthenticator(OAuthAuthenticator, metaclass=SingletonMeta):
    """Authenticator class for ZoomPhone."""

    @override
    @property
    def oauth_request_body(self) -> dict:
        """Define the OAuth request body for the AutomaticTestTap API.

        Returns:
            A dict with the request body
        """
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "account_id": self._account_id,
            "grant_type": "account_credentials",
        }

    def __init__(self, client_id: str = None, client_secret: str = None, account_id: str = None, **kwargs):
        """Initialize the authenticator.
        
        Args:
            client_id: The OAuth client ID.
            client_secret: The OAuth client secret.
            account_id: The Zoom account ID.
            **kwargs: Additional arguments passed to parent class.
        """
        self._account_id = account_id
        
        return super().__init__(
            auth_endpoint="https://zoom.us/oauth/token",
            oauth_scopes="",
            client_id=client_id,
            client_secret=client_secret,
            **kwargs
        )
