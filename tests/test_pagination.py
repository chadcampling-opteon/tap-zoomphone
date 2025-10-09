"""Tests for pagination logic."""

import logging
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from urllib.parse import urlparse, parse_qs

import pytest
from dateutil.relativedelta import relativedelta

from tap_zoomphone.pagination import (
    TokenPaginationStrategy,
    TokenBasedDateRangePaginationStrategy,
    PageCountBasedDateRangePaginationStrategy,
    SinglePageStrategy,
    ZoomDateJsonPaginator,
)


class TestTokenPaginationStrategy:
    """Test token-based pagination strategy."""

    def test_initial_request_no_token(self):
        """Test initial request with no token."""
        strategy = TokenPaginationStrategy(page_size=100)
        params = strategy.get_url_params(context=None, next_page_token=None)
        
        assert params == {"page_size": 100}

    def test_request_with_token(self):
        """Test request with next page token."""
        strategy = TokenPaginationStrategy(page_size=100)
        next_page_token = {"next_page_token": "abc123"}
        params = strategy.get_url_params(context=None, next_page_token=next_page_token)
        
        assert params == {
            "page_size": 100,
            "next_page_token": "abc123"
        }

    def test_request_with_empty_token(self):
        """Test request with empty token."""
        strategy = TokenPaginationStrategy(page_size=100)
        next_page_token = {"next_page_token": None}
        params = strategy.get_url_params(context=None, next_page_token=next_page_token)
        
        assert params == {"page_size": 100}

    def test_should_continue_with_token(self):
        """Test should_continue returns True when token exists."""
        strategy = TokenPaginationStrategy()
        mock_response = Mock()
        mock_response.json.return_value = {"next_page_token": "abc123"}
        
        assert strategy.should_continue(mock_response) is True

    def test_should_continue_without_token(self):
        """Test should_continue returns False when no token."""
        strategy = TokenPaginationStrategy()
        mock_response = Mock()
        mock_response.json.return_value = {}
        
        assert strategy.should_continue(mock_response) is False


class TestTokenBasedDateRangePaginationStrategy:
    """Test token-based date range pagination strategy."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.history_window = relativedelta(months=6)
        self.strategy = TokenBasedDateRangePaginationStrategy(
            page_size=100,
            history_window=self.history_window,
            logger=self.logger
        )

    def test_extract_pagination_data_with_token(self):
        """Test SMS Sessions data extraction with token."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/sms/sessions?from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z"
        mock_response.json.return_value = {
            "next_page_token": "abc123",
            "sms_sessions": [{"id": "1"}, {"id": "2"}]
        }
        
        data = self.strategy.extract_pagination_data(mock_response, mock_response.request.url)
        
        assert data["next_page_token"] == "abc123"
        assert data["last_from"] == "2024-01-01T00:00:00Z"
        assert data["last_to"] == "2024-01-31T23:59:59Z"
        assert data["has_more"] is True  # SMS Sessions: Only check token

    def test_extract_pagination_data_without_token(self):
        """Test SMS Sessions data extraction without token."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/sms/sessions?from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z"
        mock_response.json.return_value = {
            "sms_sessions": [{"id": "1"}]
            # No next_page_token field
        }
        
        data = self.strategy.extract_pagination_data(mock_response, mock_response.request.url)
        
        assert data["next_page_token"] is None
        assert data["has_more"] is True  # Should continue to next month since 2024-01-31 is in the past

    def test_extract_pagination_data_without_token_future_date(self):
        """Test SMS Sessions data extraction without token when date range is in the future."""
        mock_response = Mock()
        # Use a future date (next year)
        future_date = datetime.now(timezone.utc).replace(year=2026, month=1, day=31)
        future_date_str = future_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        mock_response.request.url = f"https://api.zoom.us/v2/phone/sms/sessions?from=2026-01-01T00:00:00Z&to={future_date_str}"
        mock_response.json.return_value = {
            "sms_sessions": [{"id": "1"}]
            # No next_page_token field
        }
        
        data = self.strategy.extract_pagination_data(mock_response, mock_response.request.url)
        
        assert data["next_page_token"] is None
        assert data["has_more"] is False  # Should not continue since date is in the future

    def test_extract_pagination_data_ignores_page_count(self):
        """Test that SMS Sessions strategy ignores page_count if present."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/sms/sessions"
        mock_response.json.return_value = {
            "next_page_token": "abc123",
            "page_count": 5,  # This should be ignored
            "sms_sessions": [{"id": "1"}]
        }
        
        data = self.strategy.extract_pagination_data(mock_response, mock_response.request.url)
        
        assert data["has_more"] is True  # Should use token, not page_count


class TestPageCountBasedDateRangePaginationStrategy:
    """Test page count-based date range pagination strategy."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.history_window = relativedelta(months=6)
        self.strategy = PageCountBasedDateRangePaginationStrategy(
            page_size=300,
            history_window=self.history_window,
            logger=self.logger
        )

    def test_extract_pagination_data_with_page_count(self):
        """Test Call History data extraction with page count."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/call_history?from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z"
        mock_response.json.return_value = {
            "next_page_token": "def456",
            "page_count": 5,
            "call_logs": [{"id": "1"}, {"id": "2"}]
        }
        
        data = self.strategy.extract_pagination_data(mock_response, mock_response.request.url)
        
        assert data["next_page_token"] == "def456"
        assert data["last_from"] == "2024-01-01T00:00:00Z"
        assert data["last_to"] == "2024-01-31T23:59:59Z"
        assert data["page_count"] == 5
        assert data["has_more"] is True  # Call History: Use page_count

    def test_extract_pagination_data_no_more_pages(self):
        """Test Call History data extraction when no more pages."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/call_history?from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z"
        mock_response.json.return_value = {
            "next_page_token": "def456",  # Misleading token - still present
            "page_count": 0,  # But page_count indicates no more pages
            "call_logs": [{"id": "1"}]
        }
        
        data = self.strategy.extract_pagination_data(mock_response, mock_response.request.url)
        
        assert data["next_page_token"] == "def456"  # Still extracted
        assert data["page_count"] == 0
        assert data["has_more"] is False  # Call History: Use page_count, ignore token

    def test_extract_pagination_data_ignores_misleading_token(self):
        """Test that Call History strategy ignores misleading token."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/call_history"
        mock_response.json.return_value = {
            "next_page_token": "misleading_token",  # Misleading token
            "page_count": 0,  # But page_count is 0
            "call_logs": [{"id": "1"}]
        }
        
        data = self.strategy.extract_pagination_data(mock_response, mock_response.request.url)
        
        assert data["has_more"] is False  # Should use page_count, not token

    def test_initial_request_no_token(self):
        """Test initial request with no token."""
        with patch.object(self.strategy, '_get_initial_start_date') as mock_start_date:
            mock_start_date.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
            params = self.strategy.get_url_params(context=None, next_page_token=None)
            
            assert params["page_size"] == 300
            assert "from" in params
            assert "to" in params

    def test_request_with_valid_token(self):
        """Test request with valid token and date range."""
        next_page_token = {
            "next_page_token": "abc123",
            "last_from": "2024-01-01T00:00:00Z",
            "last_to": "2024-01-31T23:59:59Z",
            "last_page_in_batch": False
        }
        params = self.strategy.get_url_params(context=None, next_page_token=next_page_token)
        
        assert params == {
            "page_size": 300,
            "next_page_token": "abc123",
            "from": "2024-01-01T00:00:00Z",
            "to": "2024-01-31T23:59:59Z"
        }

    def test_request_with_last_page_in_batch(self):
        """Test request when last page in batch."""
        next_page_token = {
            "next_page_token": "abc123",
            "last_from": "2024-01-01T00:00:00Z",
            "last_to": "2024-01-31T23:59:59Z",
            "last_page_in_batch": True
        }
        params = self.strategy.get_url_params(context=None, next_page_token=next_page_token)
        
        # Should advance to next month
        assert params["page_size"] == 300
        assert params["from"] == "2024-01-31T23:59:59Z"
        assert "to" in params
        assert params["to"] != "2024-01-31T23:59:59Z"  # Should be next month

    def test_has_valid_token(self):
        """Test _has_valid_token method."""
        # Valid token
        token = {"next_page_token": "abc123", "last_page_in_batch": False}
        assert self.strategy._has_valid_token(token) is True
        
        # Invalid token - last page in batch
        token = {"next_page_token": "abc123", "last_page_in_batch": True}
        assert self.strategy._has_valid_token(token) is False
        
        # Invalid token - no token
        token = {"last_page_in_batch": False}
        assert self.strategy._has_valid_token(token) is False

    def test_has_date_range(self):
        """Test _has_date_range method."""
        # Has date range
        token = {"last_from": "2024-01-01T00:00:00Z", "last_to": "2024-01-31T23:59:59Z"}
        assert self.strategy._has_date_range(token) is True
        
        # Missing date range
        token = {"last_from": "2024-01-01T00:00:00Z"}
        assert self.strategy._has_date_range(token) is False

    def test_calculate_next_month_end(self):
        """Test _calculate_next_month_end method."""
        last_to = "2024-01-31T23:59:59Z"
        next_month_end = self.strategy._calculate_next_month_end(last_to)
        
        # Should be February 29th (leap year) or 28th
        assert "2024-02-29" in next_month_end or "2024-02-28" in next_month_end


class TestSinglePageStrategy:
    """Test single page strategy."""

    def test_get_url_params(self):
        """Test get_url_params returns empty dict."""
        strategy = SinglePageStrategy()
        params = strategy.get_url_params(context=None, next_page_token=None)
        assert params == {}

    def test_should_continue(self):
        """Test should_continue always returns False."""
        strategy = SinglePageStrategy()
        mock_response = Mock()
        assert strategy.should_continue(mock_response) is False


class TestZoomDateJsonPaginator:
    """Test the ZoomDateJsonPaginator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.strategy = Mock()
        self.paginator = ZoomDateJsonPaginator(
            jsonpath="$.next_page_token",
            logger=self.logger,
            pagination_strategy=self.strategy
        )

    def test_get_next_with_token(self):
        """Test get_next with valid token."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/users?from=2024-01-01T00:00:00Z&to=2024-01-31T23:59:59Z"
        mock_response.json.return_value = {
            "next_page_token": "abc123",
            "page_count": 5
        }
        
        # Mock the strategy's extract_pagination_data method
        self.strategy.extract_pagination_data.return_value = {
            "next_page_token": "abc123",
            "last_from": "2024-01-01T00:00:00Z",
            "last_to": "2024-01-31T23:59:59Z",
            "page_count": 5,
            "has_more": True
        }
        
        result = self.paginator.get_next(mock_response)
        
        assert result is not None
        assert result["next_page_token"] == "abc123"
        assert result["last_from"] == "2024-01-01T00:00:00Z"
        assert result["last_to"] == "2024-01-31T23:59:59Z"
        assert result["last_page_in_batch"] is False

    def test_get_next_no_token(self):
        """Test get_next with no token."""
        mock_response = Mock()
        mock_response.request.url = "https://api.zoom.us/v2/phone/users"
        mock_response.json.return_value = {"page_count": 0}
        
        # Mock the strategy's extract_pagination_data method
        self.strategy.extract_pagination_data.return_value = {
            "next_page_token": None,
            "last_from": None,
            "last_to": None,
            "page_count": 0,
            "has_more": False
        }
        
        result = self.paginator.get_next(mock_response)
        
        assert result is None

    def test_advance_reset_sub_page_count(self):
        """Test advance resets sub_page_count when last page in batch."""
        # Make the mock strategy appear as a date range strategy
        from tap_zoomphone.pagination import TokenBasedDateRangePaginationStrategy
        self.paginator.pagination_strategy = Mock(spec=TokenBasedDateRangePaginationStrategy)
        
        self.paginator._last_seen_record = {"last_page_in_batch": True}
        self.paginator._sub_page_count = 5
        
        mock_response = Mock()
        self.paginator.advance(mock_response)
        
        assert self.paginator._sub_page_count == 1

    def test_advance_increment_sub_page_count(self):
        """Test advance increments sub_page_count when not last page."""
        # Make the mock strategy appear as a date range strategy
        from tap_zoomphone.pagination import TokenBasedDateRangePaginationStrategy
        self.paginator.pagination_strategy = Mock(spec=TokenBasedDateRangePaginationStrategy)
        
        self.paginator._last_seen_record = {"last_page_in_batch": False}
        self.paginator._sub_page_count = 2
        
        mock_response = Mock()
        self.paginator.advance(mock_response)
        
        assert self.paginator._sub_page_count == 3

    def test_has_more_future_date(self):
        """Test has_more returns True for future dates."""
        # Make the mock strategy appear as a date range strategy
        from tap_zoomphone.pagination import TokenBasedDateRangePaginationStrategy
        self.paginator.pagination_strategy = Mock(spec=TokenBasedDateRangePaginationStrategy)
        
        self.paginator._last_seen_record = {
            "page_count": 5,
            "last_to": "2025-01-01T00:00:00Z"
        }
        self.paginator._sub_page_count = 5
        
        mock_response = Mock()
        result = self.paginator.has_more(mock_response)
        
        assert result is True

    def test_has_more_past_date(self):
        """Test has_more returns False for past dates."""
        self.paginator._last_seen_record = {
            "page_count": 5,
            "last_to": "2020-01-01T00:00:00Z"
        }
        self.paginator._sub_page_count = 5
        
        mock_response = Mock()
        result = self.paginator.has_more(mock_response)
        
        assert result is False

    def test_strategy_aware_behavior(self):
        """Test that paginator behaves differently based on strategy type."""
        # Test with token strategy
        token_strategy = TokenPaginationStrategy(page_size=100)
        token_paginator = ZoomDateJsonPaginator("$.next_page_token", self.logger, token_strategy)
        token_paginator._last_seen_record = {"next_page_token": "abc123"}
        
        mock_response = Mock()
        has_more_token = token_paginator.has_more(mock_response)
        assert has_more_token is True
        
        # Test with single page strategy
        single_strategy = SinglePageStrategy()
        single_paginator = ZoomDateJsonPaginator("$.next_page_token", self.logger, single_strategy)
        
        has_more_single = single_paginator.has_more(mock_response)
        assert has_more_single is False




class TestPaginationIntegration:
    """Integration tests for pagination scenarios."""

    def test_users_stream_pagination_flow(self):
        """Test complete pagination flow for users stream."""
        strategy = TokenPaginationStrategy(page_size=100)
        
        # Initial request
        params = strategy.get_url_params(context=None, next_page_token=None)
        assert params == {"page_size": 100}
        
        # Second request with token
        next_page_token = {"next_page_token": "abc123"}
        params = strategy.get_url_params(context=None, next_page_token=next_page_token)
        assert params == {"page_size": 100, "next_page_token": "abc123"}
        
        # Third request with empty token (end of pagination)
        next_page_token = {"next_page_token": None}
        params = strategy.get_url_params(context=None, next_page_token=next_page_token)
        assert params == {"page_size": 100}

    def test_sms_sessions_stream_pagination_flow(self):
        """Test complete pagination flow for SMS sessions stream."""
        logger = Mock(spec=logging.Logger)
        history_window = relativedelta(months=6)
        strategy = TokenBasedDateRangePaginationStrategy(
            page_size=300,
            history_window=history_window,
            logger=logger
        )
        
        with patch.object(strategy, '_get_initial_start_date') as mock_start_date:
            mock_start_date.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
            
            # Initial request
            params = strategy.get_url_params(context=None, next_page_token=None)
            assert params["page_size"] == 300
            assert "from" in params
            assert "to" in params
            
            # Request with valid token and date range
            next_page_token = {
                "next_page_token": "abc123",
                "last_from": "2024-01-01T00:00:00Z",
                "last_to": "2024-01-31T23:59:59Z",
                "last_page_in_batch": False
            }
            params = strategy.get_url_params(context=None, next_page_token=next_page_token)
            assert params["next_page_token"] == "abc123"
            assert params["from"] == "2024-01-01T00:00:00Z"
            assert params["to"] == "2024-01-31T23:59:59Z"
            
            # Request when advancing to next month
            next_page_token = {
                "last_to": "2024-01-31T23:59:59Z",
                "last_page_in_batch": True
            }
            params = strategy.get_url_params(context=None, next_page_token=next_page_token)
            assert params["from"] == "2024-01-31T23:59:59Z"
            assert "2024-02" in params["to"]  # Should be next month
