#!/usr/bin/python3
"""Small local control surface for the Jingle menu-bar app.

The state writer stays in jingle_lifecycle.py so hook writes, snoozes, and
acknowledgements share its lock and atomic-save guarantees.
"""

from __future__ import annotations

import argparse
import json

from jingle_lifecycle import acknowledge_unit, snooze_unit


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--acknowledge")
    group.add_argument("--snooze")
    parser.add_argument("--seconds", type=int, default=600)
    arguments = parser.parse_args()
    if arguments.acknowledge:
        result = acknowledge_unit(arguments.acknowledge)
    else:
        result = snooze_unit(arguments.snooze, arguments.seconds)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
