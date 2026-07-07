"""Pure portfolio-action classification from price and allocation facts."""

from enum import StrEnum

from peakguard.config import AssetType
from peakguard.mdd_calc import ReviewLevel
from peakguard.portfolio_context import AllocationStatus

__all__ = ["PortfolioAction", "derive_portfolio_action"]

_ETF_ASSET_TYPES = frozenset(
    {AssetType.CORE_ETF, AssetType.BOND_ETF, AssetType.GOLD_PROXY}
)
_ALLOCATION_ELIGIBLE_LEVELS = frozenset(
    {
        ReviewLevel.WATCH,
        ReviewLevel.ATTRACTIVE,
        ReviewLevel.DEEP_DISCOUNT,
        ReviewLevel.THESIS_CHECK,
    }
)


class PortfolioAction(StrEnum):
    """Allocation guidance kept separate from price-derived review levels."""

    REBALANCE_CANDIDATE = "REBALANCE_CANDIDATE"
    ACTION_REVIEW = "ACTION_REVIEW"
    WATCH = "WATCH"
    NO_ADD = "NO_ADD"
    THESIS_CHECK = "THESIS_CHECK"


def derive_portfolio_action(
    *,
    review_level: ReviewLevel,
    allocation_status: AllocationStatus,
    asset_type: AssetType | None,
    thesis_required: bool,
) -> PortfolioAction | None:
    """Derive allocation guidance without changing the price review level.

    Allocation guardrails have highest precedence: an above-range asset is always
    ``NO_ADD`` when its price condition is eligible for allocation guidance. A
    deep-discount individual stock with explicit thesis policy requires a thesis
    check when it is not above range. Below-range ETFs become rebalance candidates;
    other below-range assets require action review. Within-range assets remain watch
    only. No action is produced for no price review or a recovery-only signal.

    Args:
        review_level: Existing price-derived review state.
        allocation_status: PortfoTrack position relative to target bounds.
        asset_type: Optional configured asset category.
        thesis_required: Explicit individual-stock thesis policy.

    Returns:
        A separate portfolio action, or ``None`` when allocation guidance does not
        apply to the price condition.
    """
    if review_level not in _ALLOCATION_ELIGIBLE_LEVELS:
        return None
    if allocation_status is AllocationStatus.ABOVE_TOLERANCE:
        return PortfolioAction.NO_ADD
    if (
        review_level is ReviewLevel.DEEP_DISCOUNT
        and asset_type is AssetType.INDIVIDUAL_STOCK
        and thesis_required
    ):
        return PortfolioAction.THESIS_CHECK
    if allocation_status is AllocationStatus.BELOW_TOLERANCE:
        if asset_type in _ETF_ASSET_TYPES:
            return PortfolioAction.REBALANCE_CANDIDATE
        return PortfolioAction.ACTION_REVIEW
    return PortfolioAction.WATCH
