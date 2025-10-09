"""REST client handling, including ZoomPhoneStream base class."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from urllib import parse
from dateutil.relativedelta import relativedelta
import decimal
import typing as t
if sys.version_info < (3, 12):
    from typing_extensions import override
else:
    from typing import override  # noqa: ICN003
from functools import cached_property
from importlib import resources

from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.pagination import BaseAPIPaginator, SinglePagePaginator  # noqa: TC002
from singer_sdk.streams import RESTStream

from tap_zoomphone.auth import ZoomPhoneAuthenticator
from tap_zoomphone.pagination import ZoomDateJsonPaginator

if t.TYPE_CHECKING:
    import requests
    from singer_sdk.helpers.types import Auth, Context


SCHEMAS_DIR = resources.files(__package__) / "schemas"


class ZoomPhoneStream(RESTStream):
    """ZoomPhone stream class."""
    _page_size = 100
    _LOG_REQUEST_METRIC_URLS = True
    _history_window = None

    # Update this value if necessary or override `get_new_paginator`.
    next_page_token_jsonpath = "$.next_page_token"  # noqa: S105
    
    def __init__(self, *args, **kwargs):
        """Initialize the stream with pagination strategy."""
        super().__init__(*args, **kwargs)
        self._pagination_strategy = self.get_pagination_strategy()
    
    def get_pagination_strategy(self):
        """Return the default pagination strategy for this stream.
        
        Subclasses should override this method to provide their specific strategy.
        """
        from tap_zoomphone.pagination import TokenPaginationStrategy
        return TokenPaginationStrategy(page_size=self._page_size)

    @property
    def url_base(self) -> str:
        """Return the API URL root, configurable via tap settings."""
        return "https://api.zoom.us/v2/phone"

    @cached_property
    def authenticator(self) -> Auth:
        """Return a new authenticator object.

        Returns:
            An authenticator instance.
        """
        return ZoomPhoneAuthenticator(
            client_id=self.config["client_id"],
            client_secret=self.config["client_secret"],
            account_id=self.config["account_id"]
        )

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed.

        Returns:
            A dictionary of HTTP headers.
        """
        return {}

    def get_new_paginator(self) -> BaseAPIPaginator:
        """Create a new pagination helper instance.

        If the source API can make use of the `next_page_token_jsonpath`
        attribute, or it contains a `X-Next-Page` header in the response
        then you can remove this method.

        If you need custom pagination that uses page numbers, "next" links, or
        other approaches, please read the guide: https://sdk.meltano.com/en/v0.25.0/guides/pagination-classes.html.

        Returns:
            A pagination helper instance.
        """
        
        return ZoomDateJsonPaginator(
            self.next_page_token_jsonpath, 
            self.logger,
            self._pagination_strategy
        )

    def get_url_params(
        self,
        context: Context | None,  # noqa: ARG002
        next_page_token: t.Any | None,  # noqa: ANN401
    ) -> dict[str, t.Any]:
        """Returns query params for Zoom API supporting differing pagination
        
            - Next Page Token (UsersStream)
            - Next Page Token and Incremental From/To dates (SmsSessions, CallHistory)
                - Call History endpoint returns page count in body and returns a next page token when there isn't any more pages
                - Sms Sessions doesn't have body data but will return a blank token
                - Zoom only allow a date range within the same month requiring batching by month
            - Single result page, handled with page_size of None on stream (CallHistoryPath)

        Args:
            context: The stream context.
            next_page_token: The next page index or value.

        Returns:
            A dictionary of URL query parameters.
        """    
        return self._pagination_strategy.get_url_params(context, next_page_token)

    def parse_response(self, response: requests.Response) -> t.Iterable[dict]:
        """Parse the response and return an iterator of result records.

        Args:
            response: The HTTP ``requests.Response`` object.

        Yields:
            Each record from the source.
        """
        yield from extract_jsonpath(
            self.records_jsonpath,
            input=response.json(parse_float=decimal.Decimal),
        )
