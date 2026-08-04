#!/usr/bin/env python3
"""Canonical Codex Harness command line entry point.

Codex Harness owns the active, local-only Codex accounting surface.  The
ledger implementation remains importable as ``token_counter`` for backwards
compatibility, while this module is the only documented command users need.
"""

from __future__ import annotations

import argparse
import sys

import token_counter
import token_counter_ui


PRODUCT_NAME = "Codex Harness"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codex_harness.py",
        description="Local, read-only Codex Harness thread accounting",
    )
    parser.add_argument(
        "command",
        choices=("scan", "summary", "ui"),
        nargs="?",
        default="summary",
        help="scan local Codex sessions, print the ledger summary, or start the UI",
    )
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    if args.command == "ui":
        return token_counter_ui.main(args.rest)

    # Reuse the audited ledger parser and accounting code.  Keeping this
    # compatibility path in one place prevents the old and new commands from
    # developing separate counting semantics.
    return token_counter.main([args.command, *args.rest])


if __name__ == "__main__":
    raise SystemExit(main())
