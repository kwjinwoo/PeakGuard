"""Tests for the PeakGuard custom error hierarchy."""

from peakguard.errors import (
    FetchError,
    NotificationError,
    PeakGuardError,
    StorageError,
)


class TestPeakGuardError:
    """Tests for the base PeakGuardError exception."""

    def test_inherits_from_exception(self) -> None:
        assert issubclass(PeakGuardError, Exception)

    def test_stores_message(self) -> None:
        error = PeakGuardError("something went wrong")
        assert str(error) == "something went wrong"


class TestFetchError:
    """Tests for the FetchError exception."""

    def test_inherits_from_peakguard_error(self) -> None:
        assert issubclass(FetchError, PeakGuardError)

    def test_stores_ticker_and_message(self) -> None:
        error = FetchError(ticker="AAPL", message="network timeout")
        assert error.ticker == "AAPL"
        assert error.message == "network timeout"

    def test_str_contains_ticker_and_message(self) -> None:
        error = FetchError(ticker="MSFT", message="rate limited")
        result = str(error)
        assert "MSFT" in result
        assert "rate limited" in result

    def test_can_be_caught_as_peakguard_error(self) -> None:
        with_caught = False
        try:
            raise FetchError(ticker="GOOG", message="connection error")
        except PeakGuardError:
            with_caught = True
        assert with_caught


class TestNotificationError:
    """Tests for the NotificationError exception."""

    def test_inherits_from_peakguard_error(self) -> None:
        assert issubclass(NotificationError, PeakGuardError)

    def test_stores_message(self) -> None:
        error = NotificationError(message="Telegram API timeout")
        assert error.message == "Telegram API timeout"

    def test_str_returns_message(self) -> None:
        error = NotificationError(message="rate limited")
        assert str(error) == "rate limited"

    def test_can_be_caught_as_peakguard_error(self) -> None:
        with_caught = False
        try:
            raise NotificationError(message="server error")
        except PeakGuardError:
            with_caught = True
        assert with_caught


class TestStorageError:
    """Tests for the StorageError exception."""

    def test_inherits_from_peakguard_error(self) -> None:
        assert issubclass(StorageError, PeakGuardError)

    def test_stores_path_and_message(self) -> None:
        error = StorageError(path="/tmp/peak_prices.json", message="file not found")
        assert error.path == "/tmp/peak_prices.json"
        assert error.message == "file not found"

    def test_str_contains_path_and_message(self) -> None:
        error = StorageError(path="/data/prices.json", message="permission denied")
        result = str(error)
        assert "/data/prices.json" in result
        assert "permission denied" in result

    def test_can_be_caught_as_peakguard_error(self) -> None:
        with_caught = False
        try:
            raise StorageError(path="/tmp/test.json", message="disk full")
        except PeakGuardError:
            with_caught = True
        assert with_caught
