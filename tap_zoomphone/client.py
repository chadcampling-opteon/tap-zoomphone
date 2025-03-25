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
        return ZoomPhoneAuthenticator.create_for_stream(self)

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
        
        return ZoomDateJsonPaginator(self.next_page_token_jsonpath, self.logger)

    def get_url_params(
        self,
        context: Context | None,  # noqa: ARG002
        next_page_token: t.Any | None,  # noqa: ANN401
    ) -> dict[str, t.Any]:
        """Returns query params for Zoom API supporting differing pagination
        
            - Next Page Token (UsersStream)
            - Next Pase Token and Incremental From/To dates (SmsSessions, CallHistory)
                - Call History endpoint returns page count in body and returns a next page token when there isn't any more pages
                - Sms Sessions doens't have body data but will return a blank token
                - Zoom only allow a date range within the same month requiring batching by month
            - Single result page, handled with page_size of None on stream (CallHistoryPath)

        Args:
            context: The stream context.
            next_page_token: The next page index or value.

        Returns:
            A dictionary of URL query parameters.
        """    
        params: dict = {}
        params["page_size"] = self._page_size
        if next_page_token:
            if next_page_token["next_page_token"] and not next_page_token["last_page_in_batch"]:
                params["next_page_token"] = next_page_token["next_page_token"]
                if self._history_window:
                    params["from"] = next_page_token["last_from"]
                    params["to"] = next_page_token["last_to"]
            elif self._history_window:
                params["from"] = next_page_token["last_to"]
                params["to"] = (datetime.fromisoformat(next_page_token["last_to"]) + relativedelta(months=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif self._history_window:
            starting_date = self.get_starting_timestamp(context)
            if not starting_date:
                starting_date = (datetime.now(timezone.utc) + relativedelta(days=1) - self._history_window).replace(hour=0, minute=0, second=0, microsecond=0)
            params["from"] = starting_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            params["to"] = (starting_date + relativedelta(months=1)).replace(day=1,hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')
            
        return params

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
    
class ZoomDateJsonPaginator(BaseAPIPaginator[t.Optional[dict]]):
    """Paginator class for APIs returning a pagination token in the response body."""
    
    # maintains page count in a date range batch
    _sub_page_count = 0

    def __init__(
        self,
        jsonpath: str,
        logger: logging.Logger,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        """Create a new paginator.

        Args:
            jsonpath: A JSONPath expression.
            args: Paginator positional arguments for base class.
            kwargs: Paginator keyword arguments for base class.
        """
        super().__init__(None, *args, **kwargs)
        self._jsonpath = jsonpath
        self.logger = logger

    @override
    def get_next(self, response: requests.Response) -> dict | None:
        """Get the next page token.

        Args:
            response: API response object.

        Returns:
            The next page token.
        """
        req_url = response.request.url
        req_params = parse.parse_qs(parse.urlparse(req_url).query)
        self.logger.debug("Params: {}".format(req_params))
        last_from = req_params.get("from", [None])[0]
        last_to = req_params.get("to", [None])[0]
        
        response_json = response.json()
        response_page_count = response_json.get("page_count")
        
        last_page_in_batch = self._sub_page_count == response_page_count
        
        self._last_seen_record = {
            "page_count":response_page_count,
            "last_page_in_batch":last_page_in_batch,
            "last_to":last_to,
        }
        
        all_matches = extract_jsonpath(self._jsonpath, response_json)
        next_page_token = next(all_matches, None)
        
        if not response_page_count and not next_page_token:
            return None
        
        result = {
            "next_page_token": next_page_token,
            "last_from": last_from,
            "last_to": last_to,
            "last_page_in_batch": last_page_in_batch
        }
        
        return result
    
    def advance(self, response):
        if self._last_seen_record and self._last_seen_record["last_page_in_batch"]:
            # reset to page 1 for new batch
            self._sub_page_count = 1
        else:
            self._sub_page_count += 1
        return super().advance(response)
    
    def has_more(self, response):
        if self._last_seen_record and self._sub_page_count == self._last_seen_record.get("page_count") and self._last_seen_record.get("last_to"):
            # to date is in future and we're on last page, no more records
            last_to_datetime = datetime.fromisoformat(self._last_seen_record["last_to"])
            return last_to_datetime < datetime.now(timezone.utc)
        
        return True
