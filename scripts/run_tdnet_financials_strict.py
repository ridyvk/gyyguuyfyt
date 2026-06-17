#!/usr/bin/env python3
"""Run the strict TDnet updater with compatibility patches."""

from __future__ import annotations

from datetime import timedelta

import update_tdnet_financials_strict as strict

# Compatibility patch for the first strict updater version.
strict.timedelta = timedelta

if __name__ == "__main__":
    raise SystemExit(strict.main())
