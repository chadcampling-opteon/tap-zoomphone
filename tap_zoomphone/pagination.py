"""Pagination logic for Zoom Phone API streams."""

from __future__ import annotations

import logging
import sys
import typing as t
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from urllib import parse

from dateutil.relativedelta import relativedelta
from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.pagination import BaseAPIPaginator

if sys.version_info < (3, 12):
    from typing_extensions import override
else:
    from typing import override  # noqa: ICN003

if t.TYPE_CHECKING:
    import requests


class PaginationStrategy(ABC):
    """Abstract base class for pagination strategies."""
    
    @abstractmethod
    def get_url_params(self, context: t.Any, next_page_token: t.Any) -> dict[str, t.Any]:
        """Get URL parameters for the next request."""
        pass
    
    @abstractmethod
    def should_continue(self, response: requests.Response) -> bool:
        """Determine if pagination should continue."""
        pass
    
    @abstractmethod
    def extract_pagination_data(self, response: requests.Response, request_url: str) -> dict[str, t.Any]:
        """Extract pagination-relevant data from response."""
        pass


class TokenPaginationStrategy(PaginationStrategy):
    """Simple token-based pagination strategy."""
    
    def __init__(self, page_size: int = 100):
        self.page_size = page_size
    
    def get_url_params(self, context: t.Any, next_page_token: t.Any) -> dict[str, t.Any]:
        """Get URL parameters for token-based pagination."""
        params = {"page_size": self.page_size}
        if next_page_token and next_page_token.get("next_page_token"):
            params["next_page_token"] = next_page_token["next_page_token"]
        return params
    
    def should_continue(self, response: requests.Response) -> bool:
        """Continue if there's a next page token."""
        return bool(response.json().get("next_page_token"))
    
    def extract_pagination_data(self, response: requests.Response, request_url: str) -> dict[str, t.Any]:
        """Extract token pagination data."""
        response_json = response.json()
        all_matches = extract_jsonpath("$.next_page_token", response_json)
        next_page_token = next(all_matches, None)
        
        return {
            "next_page_token": next_page_token,
            "has_more": bool(next_page_token)
        }


class TokenBasedDateRangePaginationStrategy(PaginationStrategy):
    """Pagination strategy that relies on next_page_token only for date range pagination."""
    
    def __init__(self, page_size: int, history_window: relativedelta, logger: logging.Logger, stream=None):
        self.page_size = page_size
        self.history_window = history_window
        self.logger = logger
        self.stream = stream
    
    def get_url_params(self, context: t.Any, next_page_token: t.Any) -> dict[str, t.Any]:
        """Get URL parameters for SMS Sessions pagination."""
        params = {"page_size": self.page_size}
        
        if next_page_token:
            if self._has_valid_token(next_page_token):
                params["next_page_token"] = next_page_token["next_page_token"]
                if self._has_date_range(next_page_token):
                    params["from"] = next_page_token["last_from"]
                    params["to"] = next_page_token["last_to"]
            elif self._should_advance_date_range(next_page_token):
                params["from"] = next_page_token["last_to"]
                params["to"] = self._calculate_next_month_end(next_page_token["last_to"])
        else:
            # Initial request
            start_date = self._get_initial_start_date(context)
            params["from"] = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            params["to"] = self._calculate_month_end(start_date).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        return params
    
    def should_continue(self, response: requests.Response) -> bool:
        """Continue if we haven't reached the current date."""
        return True  # Handled by has_more logic
    
    def extract_pagination_data(self, response: requests.Response, request_url: str) -> dict[str, t.Any]:
        """Extract SMS Sessions pagination data - relies on next_page_token only."""
        req_params = parse.parse_qs(parse.urlparse(request_url).query)
        last_from = req_params.get("from", [None])[0]
        last_to = req_params.get("to", [None])[0]
        
        response_json = response.json()
        
        # Extract next page token
        all_matches = extract_jsonpath("$.next_page_token", response_json)
        next_page_token = next(all_matches, None)
        
        # For SMS Sessions, we need to check if we should continue even without a token
        # (i.e., if we haven't reached the current date yet)
        has_more = bool(next_page_token)
        if not has_more and last_to:
            # No more pages in current date range, but check if we should advance to next month
            last_to_datetime = datetime.fromisoformat(last_to)
            has_more = last_to_datetime < datetime.now(timezone.utc)
        
        return {
            "next_page_token": next_page_token,
            "last_from": last_from,
            "last_to": last_to,
            "has_more": has_more
        }
    
    def _has_valid_token(self, next_page_token: dict) -> bool:
        """Check if we have a valid next page token."""
        return bool(next_page_token.get("next_page_token") and 
                   not next_page_token.get("last_page_in_batch", False))
    
    def _has_date_range(self, next_page_token: dict) -> bool:
        """Check if we have date range information."""
        return bool(next_page_token.get("last_from") and next_page_token.get("last_to"))
    
    def _should_advance_date_range(self, next_page_token: dict) -> bool:
        """Check if we should advance to the next date range."""
        return bool(next_page_token.get("last_to"))
    
    def _calculate_next_month_end(self, last_to: str) -> str:
        """Calculate the end of the next month."""
        last_to_date = datetime.fromisoformat(last_to)
        next_month_end = last_to_date + relativedelta(months=1)
        return next_month_end.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    def _get_starting_timestamp(self, context: t.Any) -> datetime | None:
        """Get the starting timestamp from the stream."""
        if not self.stream:
            return None
        return self.stream.get_starting_timestamp(context)
    
    def _get_initial_start_date(self, context: t.Any) -> datetime:
        """Get the initial start date for the first request."""
        starting_date = self._get_starting_timestamp(context)
        
        if starting_date:
            return starting_date
        
        # revert to full sync based on history window size
        return (datetime.now(timezone.utc) + relativedelta(days=1) - self.history_window).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    
    def _calculate_month_end(self, start_date: datetime) -> datetime:
        """Calculate the end of the month for the given start date."""
        return (start_date + relativedelta(months=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )


class PageCountBasedDateRangePaginationStrategy(PaginationStrategy):
    """Pagination strategy that relies on page_count for date range pagination, ignores misleading token."""
    
    def __init__(self, page_size: int, history_window: relativedelta, logger: logging.Logger, stream=None):
        self.page_size = page_size
        self.history_window = history_window
        self.logger = logger
        self.stream = stream
    
    def get_url_params(self, context: t.Any, next_page_token: t.Any) -> dict[str, t.Any]:
        """Get URL parameters for Call History pagination."""
        params = {"page_size": self.page_size}
        
        if next_page_token:
            if self._has_valid_token(next_page_token):
                params["next_page_token"] = next_page_token["next_page_token"]
                if self._has_date_range(next_page_token):
                    params["from"] = next_page_token["last_from"]
                    params["to"] = next_page_token["last_to"]
            elif self._should_advance_date_range(next_page_token):
                params["from"] = next_page_token["last_to"]
                params["to"] = self._calculate_next_month_end(next_page_token["last_to"])
        else:
            # Initial request
            start_date = self._get_initial_start_date(context)
            params["from"] = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            params["to"] = self._calculate_month_end(start_date).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        return params
    
    def should_continue(self, response: requests.Response) -> bool:
        """Continue if we haven't reached the current date."""
        return True  # Handled by has_more logic
    
    def extract_pagination_data(self, response: requests.Response, request_url: str) -> dict[str, t.Any]:
        """Extract Call History pagination data - relies on page_count, ignores misleading token."""
        req_params = parse.parse_qs(parse.urlparse(request_url).query)
        last_from = req_params.get("from", [None])[0]
        last_to = req_params.get("to", [None])[0]
        
        response_json = response.json()
        response_page_count = response_json.get("page_count")
        
        # Extract next page token but don't rely on it for has_more logic
        all_matches = extract_jsonpath("$.next_page_token", response_json)
        next_page_token = next(all_matches, None)
        
        has_more = bool(response_page_count is not None and response_page_count > 0)  #check page_count
        if not has_more and last_to:
            # No more pages in current date range, but check if we should advance to next month
            last_to_datetime = datetime.fromisoformat(last_to)
            has_more = last_to_datetime < datetime.now(timezone.utc)
        
        return {
            "next_page_token": next_page_token,
            "last_from": last_from,
            "last_to": last_to,
            "page_count": response_page_count,
            "has_more": has_more
        }
    
    def _has_valid_token(self, next_page_token: dict) -> bool:
        """Check if we have a valid next page token."""
        return bool(next_page_token.get("next_page_token") and 
                   not next_page_token.get("last_page_in_batch", False))
    
    def _has_date_range(self, next_page_token: dict) -> bool:
        """Check if we have date range information."""
        return bool(next_page_token.get("last_from") and next_page_token.get("last_to"))
    
    def _should_advance_date_range(self, next_page_token: dict) -> bool:
        """Check if we should advance to the next date range."""
        return bool(next_page_token.get("last_to"))
    
    def _calculate_next_month_end(self, last_to: str) -> str:
        """Calculate the end of the next month."""
        last_to_date = datetime.fromisoformat(last_to)
        next_month_end = last_to_date + relativedelta(months=1)
        return next_month_end.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    def _get_starting_timestamp(self, context: t.Any) -> datetime | None:
        """Get the starting timestamp from the stream."""
        if not self.stream:
            return None
        return self.stream.get_starting_timestamp(context)
    
    def _get_initial_start_date(self, context: t.Any) -> datetime:
        """Get the initial start date for the first request."""
        starting_date = self._get_starting_timestamp(context)
        
        if starting_date:
            return starting_date
        
        # revert to full sync based on history window size
        return (datetime.now(timezone.utc) + relativedelta(days=1) - self.history_window).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    
    def _calculate_month_end(self, start_date: datetime) -> datetime:
        """Calculate the end of the month for the given start date."""
        return (start_date + relativedelta(months=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )


class SinglePageStrategy(PaginationStrategy):
    """Strategy for single page requests (no pagination)."""
    
    def get_url_params(self, context: t.Any, next_page_token: t.Any) -> dict[str, t.Any]:
        """No pagination parameters needed."""
        return {}
    
    def should_continue(self, response: requests.Response) -> bool:
        """Never continue for single page requests."""
        return False
    
    def extract_pagination_data(self, response: requests.Response, request_url: str) -> dict[str, t.Any]:
        """No pagination data for single page requests."""
        return {
            "next_page_token": None,
            "has_more": False
        }


class ZoomDateJsonPaginator(BaseAPIPaginator[t.Optional[dict]]):
    """Enhanced paginator for Zoom API with better testability."""

    def __init__(
        self,
        jsonpath: str,
        logger: logging.Logger,
        pagination_strategy: PaginationStrategy,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        """Create a new paginator.

        Args:
            jsonpath: A JSONPath expression.
            pagination_strategy: The pagination strategy to use.
            args: Paginator positional arguments for base class.
            kwargs: Paginator keyword arguments for base class.
        """
        super().__init__(None, *args, **kwargs)
        self._jsonpath = jsonpath
        self.logger = logger
        self.pagination_strategy = pagination_strategy
        self._sub_page_count = 0
        self._last_seen_record: dict[str, t.Any] = {}

    @override
    def get_next(self, response: requests.Response) -> dict | None:
        """Get the next page token using the pagination strategy.

        Args:
            response: API response object.

        Returns:
            The next page token.
        """
        req_url = response.request.url
        self.logger.debug("Request URL: {}".format(req_url))
        
        # Delegate to strategy to extract pagination data
        pagination_data = self.pagination_strategy.extract_pagination_data(response, req_url)
        
        # Store data for advance/has_more logic
        self._last_seen_record = pagination_data
        
        # Return appropriate next page token based on strategy
        if not pagination_data.get("has_more"):
            return None
            
        result = {
            "next_page_token": pagination_data.get("next_page_token"),
            "last_from": pagination_data.get("last_from"),
            "last_to": pagination_data.get("last_to"),
            "last_page_in_batch": self._is_last_page_in_batch(pagination_data)
        }
        self.logger.debug(f"[{getattr(self, 'stream_name', getattr(self, 'name', None))}] Returning pagination object: {result}")
        return result

    def advance(self, response):
        """Advance the pagination state based on strategy."""
        if isinstance(self.pagination_strategy, (TokenBasedDateRangePaginationStrategy, PageCountBasedDateRangePaginationStrategy)):
            # Date range strategies handle page counting
            if self._last_seen_record and self._last_seen_record.get("last_page_in_batch"):
                self._sub_page_count = 1  # Reset for new batch
            else:
                self._sub_page_count += 1
        else:
            # Other strategies don't need page counting
            pass
        
        return super().advance(response)

    def continue_if_empty(self, response: requests.Response) -> bool:
        """Continue pagination even if the response is empty."""
        return True

    def has_more(self, response):
        """Determine if there are more pages based on strategy."""
        if isinstance(self.pagination_strategy, (TokenBasedDateRangePaginationStrategy, PageCountBasedDateRangePaginationStrategy)):
            # Date range strategies check date boundaries
            return self._has_more_date_range()
        elif isinstance(self.pagination_strategy, TokenPaginationStrategy):
            # Token strategy checks for next token
            return bool(self._last_seen_record.get("next_page_token"))
        else:
            # Single page strategy never has more
            return False
    
    def _is_last_page_in_batch(self, pagination_data: dict) -> bool:
        """Determine if this is the last page in a date range batch."""
        if isinstance(self.pagination_strategy, (TokenBasedDateRangePaginationStrategy, PageCountBasedDateRangePaginationStrategy)):
            page_count = pagination_data.get("page_count", 0)
            return self._sub_page_count == page_count
        return False

    def _has_more_date_range(self) -> bool:
        """Check if there are more pages in date range pagination."""
        if (self._last_seen_record and 
            self._sub_page_count == self._last_seen_record.get("page_count") and 
            self._last_seen_record.get("last_to")):
            # Check if we've reached the current date
            last_to_datetime = datetime.fromisoformat(self._last_seen_record["last_to"])
            return last_to_datetime < datetime.now(timezone.utc)
        return True


