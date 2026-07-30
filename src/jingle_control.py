#!/usr/bin/python3
"""Small local control surface for the Jingle menu-bar app.

The state writer stays in jingle_lifecycle.py so hook writes, snoozes, and
acknowledgements share its lock and atomic-save guarantees.
"""

from __future__ import annotations

import argparse
import json

from jingle_lifecycle import acknowledge_unit, quarantine_historical_completion_noise, snooze_unit


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--acknowledge")
    group.add_argument("--snooze")
    group.add_argument("--quarantine-historical-completions", action="store_true")
    parser.add_argument("--seconds", type=int, default=600)
    arguments = parser.parse_args()
    if arguments.acknowledge:
        result = acknowledge_unit(arguments.acknowledge)
    elif arguments.snooze:
        result = snooze_unit(arguments.snooze, arguments.seconds)
    else:
        result = quarantine_historical_completion_noise()
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
