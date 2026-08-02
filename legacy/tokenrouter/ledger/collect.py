"""Read local Claude Code and Codex JSONL logs into one record schema."""

import argparse
import json
from pathlib import Path

from .prices import claude_prices, codex_prices, cost_cents

HOME = Path.home()
CLAUDE_ROOT = HOME / ".claude" / "projects"
CODEX_ROOTS = (HOME / ".codex" / "sessions", HOME / ".codex" / "archived_sessions")


def _number(value):
    """Treat malformed or negative token counts as zero rather than guessing."""
    return value if isinstance(value, int) and value > 0 else 0


def _json_lines(path):
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _hour_bucket(iso_timestamp):
    """'2026-07-28T09:15:02.123Z' → '2026-07-28T09'; empty string if malformed."""
    if isinstance(iso_timestamp, str) and len(iso_timestamp) >= 13 and iso_timestamp[10] == "T":
        return iso_timestamp[:13]
    return ""


def collect_claude(root=CLAUDE_ROOT):
    """Return all Claude usage events, keyed by their project-directory name."""
    records = []
    directories = sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []
    for directory in directories:
        for path in sorted(directory.rglob("*.jsonl")):
            for event in _json_lines(path):
                message = event.get("message")
                usage = message.get("usage") if isinstance(message, dict) else None
                if not isinstance(usage, dict):
                    continue
                input_tokens = _number(usage.get("input_tokens"))
                output_tokens = _number(usage.get("output_tokens"))
                cache_write_tokens = _number(usage.get("cache_creation_input_tokens"))
                cache_read_tokens = _number(usage.get("cache_read_input_tokens"))
                if not any((input_tokens, output_tokens, cache_write_tokens, cache_read_tokens)):
                    continue
                model = message.get("model") if isinstance(message.get("model"), str) else ""
                records.append({
                    "channel": "claude",
                    "hour": _hour_bucket(event.get("timestamp")),
                    "source_key": directory.name,
                    "source_file": str(path),
                    "model": model,
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cache_read_tokens,
                    "cache_write_tokens": cache_write_tokens,
                    "output_tokens": output_tokens,
                    "cost_cents": cost_cents(
                        input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,
                        claude_prices(model),
                    ),
                })
    return {"dirs": len(directories), "records": records}


def extract_codex_file(path):
    """Return the final cumulative usage from one file, never a sum of events."""
    cwd = ""
    last_usage = None
    for event in _json_lines(path):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if event.get("type") == "session_meta":
            candidate = payload.get("cwd")
            if isinstance(candidate, str):
                cwd = candidate
        info = payload.get("info")
        usage = info.get("total_token_usage") if isinstance(info, dict) else None
        if isinstance(usage, dict):
            last_usage = usage
    if last_usage is None:
        return cwd, None
    return cwd, {
        "input_tokens": _number(last_usage.get("input_tokens")),
        "cached_input_tokens": _number(last_usage.get("cached_input_tokens")),
        "output_tokens": _number(last_usage.get("output_tokens")),
    }


def collect_codex(roots=CODEX_ROOTS):
    """Return exactly one record per Codex JSONL file, including archived files."""
    paths = []
    for root in roots:
        if root.exists():
            paths.extend(root.rglob("*.jsonl"))
    records = []
    for path in sorted(paths):
        cwd, usage = extract_codex_file(path)
        usage = usage or {}
        input_tokens = usage.get("input_tokens", 0)
        cached_input_tokens = min(usage.get("cached_input_tokens", 0), input_tokens)
        output_tokens = usage.get("output_tokens", 0)
        fresh_input_tokens = input_tokens - cached_input_tokens
        # 文件名形如 rollout-2026-03-04T12-21-41-<uuid>.jsonl —— 会话起始时刻
        stem = path.name
        hour = ""
        if stem.startswith("rollout-") and len(stem) >= 21 and stem[18] == "T":
            hour = stem[8:18] + "T" + stem[19:21]
        records.append({
            "channel": "codex",
            "hour": hour,
            "source_key": cwd,
            "source_file": str(path),
            "model": "codex-default",
            "input_tokens": fresh_input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "cache_write_tokens": 0,
            "output_tokens": output_tokens,
            "cost_cents": cost_cents(
                fresh_input_tokens, output_tokens, 0, cached_input_tokens,
                codex_prices(),
            ),
        })
    return {"files": len(paths), "records": records}


def collect_all():
    return {"claude": collect_claude(), "codex": collect_codex()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect local model-usage logs.")
    parser.add_argument("--json", action="store_true", help="print the complete normalized record stream")
    args = parser.parse_args(argv)
    data = collect_all()
    if args.json:
        print(json.dumps(data, ensure_ascii=False))
    else:
        print("Claude directories: {}".format(data["claude"]["dirs"]))
        print("Codex files: {}".format(data["codex"]["files"]))


if __name__ == "__main__":
    main()
