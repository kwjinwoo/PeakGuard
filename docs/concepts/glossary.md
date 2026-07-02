---
id: glossary
title: Glossary
type: reference
status: active
related:
  - domain-model.md
  - alerts/README.md
---

# Glossary

- **ATH**: In PeakGuard, the highest closing price inside the current 365-calendar-day window. It is not a lifetime high.
- **Bounce from bottom**: Percentage rise from the lowest close in the current history window to the current close.
- **Bootstrap**: Initial one-year history fetch for a ticker with no stored records.
- **Closing price**: End-of-session price returned by yfinance and stored as one daily observation.
- **MDD**: Percentage decline from rolling ATH to the current close.
- **Reference date**: Trading date used as the endpoint of metric calculations and the rolling window.
- **Rolling window**: Inclusive date range from `reference date - 365 days` through the reference date.
- **Threshold breach**: A metric meeting or exceeding an inclusive configured boundary.
- **Work note**: A concise record of a difficulty encountered during coding or LLM-assisted work that may help a future task.
