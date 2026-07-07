"""Table-driven tests for portfolio-action classification."""

import pytest

from peakguard.config import AssetType
from peakguard.mdd_calc import ReviewLevel
from peakguard.portfolio_action import PortfolioAction, derive_portfolio_action
from peakguard.portfolio_context import AllocationStatus


@pytest.mark.parametrize(
    ("review_level", "status", "asset_type", "thesis_required", "expected"),
    [
        (
            ReviewLevel.NONE,
            AllocationStatus.BELOW_TOLERANCE,
            AssetType.CORE_ETF,
            False,
            None,
        ),
        (
            ReviewLevel.RECOVERY_WATCH,
            AllocationStatus.BELOW_TOLERANCE,
            AssetType.CORE_ETF,
            False,
            None,
        ),
        (
            ReviewLevel.DEEP_DISCOUNT,
            AllocationStatus.ABOVE_TOLERANCE,
            AssetType.INDIVIDUAL_STOCK,
            True,
            PortfolioAction.NO_ADD,
        ),
        (
            ReviewLevel.ATTRACTIVE,
            AllocationStatus.ABOVE_TOLERANCE,
            AssetType.CORE_ETF,
            False,
            PortfolioAction.NO_ADD,
        ),
        (
            ReviewLevel.DEEP_DISCOUNT,
            AllocationStatus.BELOW_TOLERANCE,
            AssetType.INDIVIDUAL_STOCK,
            True,
            PortfolioAction.THESIS_CHECK,
        ),
        (
            ReviewLevel.DEEP_DISCOUNT,
            AllocationStatus.WITHIN_TOLERANCE,
            AssetType.INDIVIDUAL_STOCK,
            True,
            PortfolioAction.THESIS_CHECK,
        ),
        (
            ReviewLevel.ATTRACTIVE,
            AllocationStatus.BELOW_TOLERANCE,
            AssetType.CORE_ETF,
            False,
            PortfolioAction.REBALANCE_CANDIDATE,
        ),
        (
            ReviewLevel.WATCH,
            AllocationStatus.BELOW_TOLERANCE,
            AssetType.BOND_ETF,
            False,
            PortfolioAction.REBALANCE_CANDIDATE,
        ),
        (
            ReviewLevel.DEEP_DISCOUNT,
            AllocationStatus.BELOW_TOLERANCE,
            AssetType.GOLD_PROXY,
            False,
            PortfolioAction.REBALANCE_CANDIDATE,
        ),
        (
            ReviewLevel.WATCH,
            AllocationStatus.BELOW_TOLERANCE,
            AssetType.INDIVIDUAL_STOCK,
            False,
            PortfolioAction.ACTION_REVIEW,
        ),
        (
            ReviewLevel.ATTRACTIVE,
            AllocationStatus.BELOW_TOLERANCE,
            None,
            False,
            PortfolioAction.ACTION_REVIEW,
        ),
        (
            ReviewLevel.ATTRACTIVE,
            AllocationStatus.WITHIN_TOLERANCE,
            AssetType.CORE_ETF,
            False,
            PortfolioAction.WATCH,
        ),
        (
            ReviewLevel.WATCH,
            AllocationStatus.WITHIN_TOLERANCE,
            AssetType.INDIVIDUAL_STOCK,
            False,
            PortfolioAction.WATCH,
        ),
    ],
)
def test_derive_portfolio_action_table(
    review_level: ReviewLevel,
    status: AllocationStatus,
    asset_type: AssetType | None,
    thesis_required: bool,
    expected: PortfolioAction | None,
) -> None:
    result = derive_portfolio_action(
        review_level=review_level,
        allocation_status=status,
        asset_type=asset_type,
        thesis_required=thesis_required,
    )

    assert result is expected


def test_portfolio_action_is_distinct_from_review_level() -> None:
    assert PortfolioAction.NO_ADD is not ReviewLevel.DEEP_DISCOUNT
    assert PortfolioAction.THESIS_CHECK.value != ReviewLevel.THESIS_CHECK.value
