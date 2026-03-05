"""PeakGuard CLI entry point.

Usage:
    python src/main.py
"""

import logging
import sys

from peakguard.main import run


def main() -> None:
    """Configure logging and execute the MDD check pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        run()
    except Exception:
        logging.getLogger(__name__).exception("Fatal error during MDD check")
        sys.exit(1)


if __name__ == "__main__":
    main()
