#!/usr/bin/env python3
"""Compatibility entry point for the Codex Harness local UI."""

from __future__ import annotations

import sys

import token_counter_ui


if __name__ == "__main__":
    raise SystemExit(token_counter_ui.main(sys.argv[1:]))
