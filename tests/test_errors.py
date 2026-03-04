"""Tests for the PeakGuard custom error hierarchy."""

from errors import FetchError, PeakGuardError


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
