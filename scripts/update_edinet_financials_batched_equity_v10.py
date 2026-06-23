#!/usr/bin/env python3
"""Run the EDINET annual batch with safer equity denominator priority.

The base extractor keeps the broad EDINET tag list for compatibility. This
workflow wrapper narrows the batched production run so equity-ratio and ROE
fallback calculations prefer net assets over shareholders' equity when an
explicit disclosed equity ratio is unavailable.
"""

from __future__ import annotations

import update_edinet_financials as edinet
import update_edinet_financials_batched as batched

DATA_MODEL_VERSION = 10

# In Japanese GAAP filings, ShareholdersEquity can exclude valuation/translation
# differences that are part of net assets. For fallback equity-ratio and ROE
# denominators, prefer net assets before shareholders' equity to avoid impossible
# equity ratios above 100% caused by a too-narrow denominator proxy.
EQUITY_PRIORITY = (
    "EquityAttributableToOwnersOfParent",
    "EquityAttributableToOwnersOfParentIFRS",
    "Equity",
    "EquityIFRS",
    "NetAssets",
    "NetAssetsSummaryOfBusinessResults",
    "ShareholdersEquity",
    "EquityAttributableToOwnersOfParentSummaryOfBusinessResults",
    "EquityUSGAAP",
    "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    "EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults",
)


def install_equity_priority() -> None:
    batched.DATA_MODEL_VERSION = DATA_MODEL_VERSION
    batched.STRICT_FACT_NAMES = {
        **batched.STRICT_FACT_NAMES,
        "equity": tuple(
            name for name in EQUITY_PRIORITY if name in edinet.FACT_NAMES["equity"]
        ),
    }


def main() -> int:
    install_equity_priority()
    return batched.main()


if __name__ == "__main__":
    raise SystemExit(main())
