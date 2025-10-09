"""Integration tests for stream pagination."""

import logging
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from dateutil.relativedelta import relativedelta

import pytest

from tap_zoomphone.client import ZoomPhoneStream
from tap_zoomphone.streams import (
    UsersStream,
    SmsSessionsStream,
    CallHistoryStream,
    CallHistoryPathStream,
)
from tap_zoomphone.pagination import (
    TokenPaginationStrategy,
    TokenBasedDateRangePaginationStrategy,
    PageCountBasedDateRangePaginationStrategy,
    SinglePageStrategy,
)


class TestStreamPaginationIntegration:
    """Integration tests for stream pagination."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_tap = Mock()
        self.mock_tap.config = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "account_id": "test_account_id"
        }

    def test_users_stream_pagination_strategy(self):
        """Test that UsersStream uses token pagination strategy."""
        stream = UsersStream(self.mock_tap)
        
        assert isinstance(stream._pagination_strategy, TokenPaginationStrategy)
        assert stream._pagination_strategy.page_size == 100

    def test_sms_sessions_stream_pagination_strategy(self):
        """Test that SmsSessionsStream uses token-based date range pagination strategy."""
        stream = SmsSessionsStream(self.mock_tap)
        
        assert isinstance(stream._pagination_strategy, TokenBasedDateRangePaginationStrategy)
        assert stream._pagination_strategy.page_size == 100
        assert stream._pagination_strategy.history_window == relativedelta(months=6)

    def test_call_history_stream_pagination_strategy(self):
        """Test that CallHistoryStream uses page count-based date range pagination strategy."""
        stream = CallHistoryStream(self.mock_tap)
        
        assert isinstance(stream._pagination_strategy, PageCountBasedDateRangePaginationStrategy)
        assert stream._pagination_strategy.page_size == 300
        assert stream._pagination_strategy.history_window == relativedelta(months=6)

    def test_call_history_path_stream_pagination_strategy(self):
        """Test that CallHistoryPathStream uses single page strategy."""
        stream = CallHistoryPathStream(self.mock_tap)
        
        assert isinstance(stream._pagination_strategy, SinglePageStrategy)

    def test_users_stream_url_params(self):
        """Test UsersStream URL parameter generation."""
        stream = UsersStream(self.mock_tap)
        
        # Initial request
        params = stream.get_url_params(context=None, next_page_token=None)
        assert params == {"page_size": 100}
        
        # Request with token
        next_page_token = {"next_page_token": "abc123"}
        params = stream.get_url_params(context=None, next_page_token=next_page_token)
        assert params == {"page_size": 100, "next_page_token": "abc123"}

    def test_sms_sessions_stream_url_params(self):
        """Test SmsSessionsStream URL parameter generation."""
        stream = SmsSessionsStream(self.mock_tap)
        
        with patch.object(stream._pagination_strategy, '_get_initial_start_date') as mock_start_date:
            mock_start_date.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
            
            # Initial request
            params = stream.get_url_params(context=None, next_page_token=None)
            assert params["page_size"] == 100
            assert "from" in params
            assert "to" in params

    def test_call_history_stream_url_params(self):
        """Test CallHistoryStream URL parameter generation."""
        stream = CallHistoryStream(self.mock_tap)
        
        with patch.object(stream._pagination_strategy, '_get_initial_start_date') as mock_start_date:
            mock_start_date.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
            
            # Initial request
            params = stream.get_url_params(context=None, next_page_token=None)
            assert params["page_size"] == 300
            assert "from" in params
            assert "to" in params

    def test_call_history_path_stream_url_params(self):
        """Test CallHistoryPathStream URL parameter generation."""
        stream = CallHistoryPathStream(self.mock_tap)
        
        # Should return empty params
        params = stream.get_url_params(context=None, next_page_token=None)
        assert params == {}

    def test_paginator_creation(self):
        """Test that streams create the correct paginator type."""
        stream = UsersStream(self.mock_tap)
        paginator = stream.get_new_paginator()
        
        from tap_zoomphone.pagination import ZoomDateJsonPaginator
        assert isinstance(paginator, ZoomDateJsonPaginator)
        assert paginator.pagination_strategy == stream._pagination_strategy

    def test_stream_initialization_with_different_configs(self):
        """Test that streams initialize correctly with different configurations."""
        # Test with custom page size
        class CustomUsersStream(UsersStream):
            _page_size = 200
        
        stream = CustomUsersStream(self.mock_tap)
        assert stream._pagination_strategy.page_size == 200

    def test_stream_initialization_with_custom_history_window(self):
        """Test that streams initialize correctly with custom history window."""
        class CustomSmsStream(SmsSessionsStream):
            _history_window = relativedelta(months=12)
        
        stream = CustomSmsStream(self.mock_tap)
        assert stream._pagination_strategy.history_window == relativedelta(months=12)

    def test_stream_pagination_strategy_declaration(self):
        """Test that streams declare their own pagination strategies."""
        # Test that each stream returns the correct strategy type
        users_stream = UsersStream(self.mock_tap)
        strategy = users_stream.get_pagination_strategy()
        assert isinstance(strategy, TokenPaginationStrategy)
        
        sms_stream = SmsSessionsStream(self.mock_tap)
        strategy = sms_stream.get_pagination_strategy()
        assert isinstance(strategy, TokenBasedDateRangePaginationStrategy)
        
        call_history_stream = CallHistoryStream(self.mock_tap)
        strategy = call_history_stream.get_pagination_strategy()
        assert isinstance(strategy, PageCountBasedDateRangePaginationStrategy)
        
        call_history_path_stream = CallHistoryPathStream(self.mock_tap)
        strategy = call_history_path_stream.get_pagination_strategy()
        assert isinstance(strategy, SinglePageStrategy)

    def test_error_handling_in_stream_initialization(self):
        """Test error handling when creating streams with invalid configurations."""
        # Test that streams handle missing required parameters gracefully
        # This test is now less relevant since streams declare their own strategies
        # but we can test that the base class provides a default strategy
        class TestStream(ZoomPhoneStream):
            name = "test"
        
        stream = TestStream(self.mock_tap)
        strategy = stream.get_pagination_strategy()
        assert isinstance(strategy, TokenPaginationStrategy)

    def test_stream_pagination_consistency(self):
        """Test that pagination behavior is consistent across multiple requests."""
        stream = UsersStream(self.mock_tap)
        
        # Simulate multiple pagination requests
        next_page_token = None
        for i in range(3):
            params = stream.get_url_params(context=None, next_page_token=next_page_token)
            
            if i == 0:
                # First request should have no token
                assert "next_page_token" not in params
            else:
                # Subsequent requests should have token
                assert "next_page_token" in params
            
            # Simulate getting a token for next request
            next_page_token = {"next_page_token": f"token_{i}"}

    def test_date_range_pagination_month_boundaries(self):
        """Test that date range pagination handles month boundaries correctly."""
        stream = SmsSessionsStream(self.mock_tap)
        
        # Test advancing from one month to the next
        next_page_token = {
            "last_to": "2024-01-31T23:59:59Z",
            "last_page_in_batch": True
        }
        
        params = stream.get_url_params(context=None, next_page_token=next_page_token)
        
        # Should advance to next month
        assert params["from"] == "2024-01-31T23:59:59Z"
        assert "2024-02" in params["to"]  # Should be February

    def test_pagination_with_context(self):
        """Test that pagination works correctly with stream context."""
        stream = CallHistoryStream(self.mock_tap)
        context = {"id": "test_call_id"}
        
        with patch.object(stream._pagination_strategy, '_get_initial_start_date') as mock_start_date:
            mock_start_date.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
            
            params = stream.get_url_params(context=context, next_page_token=None)
            assert params["page_size"] == 300
            assert "from" in params
            assert "to" in params
