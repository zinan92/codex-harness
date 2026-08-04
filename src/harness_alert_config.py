#!/usr/bin/env python3
"""Safe editing helpers for the optional Codex Harness notify callback.

Codex stores ``notify`` as a one-line TOML array.  The Computer Use callback
supports ``--previous-notify`` so Harness can be added without replacing the
existing system notification.  These helpers deliberately reject unknown
callback shapes instead of guessing or overwriting user configuration.
"""

from __future__ import annotations

import json
import re
import tomllib


class NotifyConfigError(ValueError):
    """The current notify callback cannot be chained safely."""


NOTIFY_LINE = re.compile(r"(?m)^notify\s*=\s*(\[.*\])\s*$")
HARNESS_BASENAMES = {"codex_harness_notify.py", "codex_spoken_notify.py"}


def _parse_array(array_text: str) -> list[str]:
    try:
        value = tomllib.loads(f"notify = {array_text}\n")["notify"]
    except (tomllib.TOMLDecodeError, KeyError) as exc:
        raise NotifyConfigError("notify is not a valid TOML array") from exc
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise NotifyConfigError("notify must be an array of strings")
    return value


def read_notify(text: str) -> list[str] | None:
    match = NOTIFY_LINE.search(text)
    if match:
        return _parse_array(match.group(1))
    # A multiline or commented notify value needs a TOML-aware editor. Never
    # mistake that shape for an absent setting and create duplicate keys.
    if re.search(r"(?m)^\s*notify\s*=", text):
        raise NotifyConfigError("notify must be a single-line TOML array")
    return None


def _previous_args(values: list[str]) -> tuple[list[str], list[str]]:
    if "--previous-notify" not in values:
        return values, []
    index = values.index("--previous-notify")
    if index + 1 >= len(values):
        raise NotifyConfigError("--previous-notify has no value")
    try:
        previous = json.loads(values[index + 1])
    except json.JSONDecodeError as exc:
        raise NotifyConfigError("--previous-notify is not JSON") from exc
    if not isinstance(previous, list) or any(not isinstance(item, str) for item in previous):
        raise NotifyConfigError("--previous-notify must contain an array of strings")
    if index + 2 != len(values):
        raise NotifyConfigError("unexpected arguments after --previous-notify")
    return values[:index], previous


def _is_harness(value: str, notifier_path: str) -> bool:
    return value == notifier_path or any(value.endswith("/" + name) for name in HARNESS_BASENAMES)


def _is_sky_turn_ended(values: list[str]) -> bool:
    return bool(values) and values[0].endswith("SkyComputerUseClient") and "turn-ended" in values[1:]


def _json_toml_array(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _replace_line(text: str, values: list[str]) -> str:
    replacement = f"notify = {_json_toml_array(values)}"
    if NOTIFY_LINE.search(text):
        return NOTIFY_LINE.sub(replacement, text, count=1)
    return replacement + "\n" + text


def add_notifier(text: str, notifier_path: str) -> str:
    """Add the Harness notifier while preserving the known notify chain."""
    current = read_notify(text)
    if current is None:
        return _replace_line(text, [notifier_path])
    if current == [notifier_path]:
        return _replace_line(text, current)
    if len(current) == 1 and _is_harness(current[0], notifier_path):
        return _replace_line(text, [notifier_path])

    base, previous = _previous_args(current)
    if _is_sky_turn_ended(base):
        previous = [item for item in previous if not _is_harness(item, notifier_path)]
        previous.append(notifier_path)
        return _replace_line(text, base + ["--previous-notify", json.dumps(previous, ensure_ascii=False)])

    raise NotifyConfigError("refusing to replace an unknown notify callback")


def remove_notifier(text: str, notifier_path: str) -> str:
    """Remove only the Harness callback, retaining all other notify values."""
    current = read_notify(text)
    if current is None:
        return text
    if len(current) == 1 and _is_harness(current[0], notifier_path):
        return NOTIFY_LINE.sub("", text, count=1).lstrip("\n")

    base, previous = _previous_args(current)
    if not _is_sky_turn_ended(base):
        if any(_is_harness(item, notifier_path) for item in current):
            raise NotifyConfigError("refusing to remove Harness from an unknown notify shape")
        return text
    remaining = [item for item in previous if not _is_harness(item, notifier_path)]
    values = base if not remaining else base + ["--previous-notify", json.dumps(remaining, ensure_ascii=False)]
    return _replace_line(text, values)
