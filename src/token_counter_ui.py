#!/usr/bin/env python3
"""A local-only visual projection of Token Counter's private thread ledger."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_STATE_PATH = Path.home() / ".codex" / "token-counter" / "threads.json"


def read_state(path: Path) -> dict[str, Any] | None:
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return candidate if isinstance(candidate, dict) and isinstance(candidate.get("threads"), dict) else None


def token_label(value: object) -> str:
    if not isinstance(value, int) or value < 0:
        return "—"
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= divisor:
            return f"{value / divisor:.1f}{suffix}"
    return f"{value:,}"


def time_label(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return datetime.fromtimestamp(value, tz=timezone.utc).astimezone().strftime("%m-%d %H:%M")


def project_totals(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for thread in threads:
        project = thread.get("project") if isinstance(thread.get("project"), dict) else {}
        key = str(project.get("project_id") or "uncategorized")
        bucket = buckets.setdefault(key, {"id": key, "name": str(project.get("name") or "Uncategorized"), "threads": 0, "available": 0, "tokens": 0})
        bucket["threads"] += 1
        if thread.get("status") == "available":
            bucket["available"] += 1
            bucket["tokens"] += int(thread.get("total_tokens") or 0)
    return sorted(buckets.values(), key=lambda item: (-item["tokens"], item["name"]))


def daily_totals(threads: list[dict[str, Any]]) -> list[tuple[str, int]]:
    buckets: dict[str, int] = defaultdict(int)
    for thread in threads:
        for day, usage in (thread.get("daily") or {}).items():
            if isinstance(usage, dict):
                buckets[str(day)] += int(usage.get("total_tokens") or 0)
    return sorted(buckets.items())[-7:]


def render(state: dict[str, Any] | None, state_path: Path) -> str:
    if state is None:
        body = f"""<main class=\"empty\"><p class=\"eyebrow\">LOCAL LEDGER</p><h1>No ledger found.</h1><p>Run <code>token_counter.py scan</code> first. Expected: <code>{escape(str(state_path))}</code></p></main>"""
        return page("Token Counter", body)
    threads = [row for row in state["threads"].values() if isinstance(row, dict)]
    available = [row for row in threads if row.get("status") == "available"]
    total = sum(int(row.get("total_tokens") or 0) for row in available)
    daily = daily_totals(threads)
    max_daily = max((tokens for _, tokens in daily), default=1)
    daily_rows = "".join(
        f"<div class=\"day\"><span>{escape(day[5:])}</span><i style=\"--w:{max(3, round(tokens / max_daily * 100))}%\"></i><b>{token_label(tokens)}</b></div>"
        for day, tokens in daily
    ) or "<p class=\"muted\">No dated usage yet.</p>"
    projects = "".join(
        f"<tr><td>{escape(item['name'])}</td><td>{item['threads']}</td><td>{item['available']}</td><td>{token_label(item['tokens'])}</td></tr>"
        for item in project_totals(threads)
    ) or "<tr><td colspan=\"4\">No project records yet.</td></tr>"
    recent = sorted(threads, key=lambda row: float(row.get("ended_at") or row.get("started_at") or 0), reverse=True)[:18]
    thread_rows = "".join(
        "<tr>"
        f"<td><code>{escape(str(row.get('thread_id') or 'unknown')[:12])}</code></td>"
        f"<td>{escape(str((row.get('project') or {}).get('name') or 'Uncategorized'))}</td>"
        f"<td class=\"status {escape(str(row.get('status') or 'unavailable'))}\">{escape(str(row.get('status') or 'unavailable'))}</td>"
        f"<td>{token_label(row.get('total_tokens'))}</td><td>{time_label(row.get('ended_at') or row.get('started_at'))}</td>"
        "</tr>"
        for row in recent
    ) or "<tr><td colspan=\"5\">No thread records yet.</td></tr>"
    generated = escape(str(state.get("generated_at") or "unknown"))
    body = f"""
<main>
  <header><div><p class=\"eyebrow\">TOKEN COUNTER / LOCAL ONLY</p><h1>Thread ledger</h1><p class=\"sub\">A quiet accounting surface for completed Codex work.</p></div><div class=\"stamp\">Last scan<br><b>{generated}</b></div></header>
  <section class=\"metrics\"><div><span>Tracked threads</span><strong>{len(threads):,}</strong></div><div><span>Usage available</span><strong>{len(available):,}</strong></div><div><span>Total tokens</span><strong>{token_label(total)}</strong></div><div><span>Timezone</span><strong>{escape(str(state.get('reporting_timezone') or 'Asia/Shanghai'))}</strong></div></section>
  <section class=\"grid\"><article><h2>Seven-day trace</h2><div class=\"bars\">{daily_rows}</div></article><article><h2>By product</h2><table><thead><tr><th>Product</th><th>Threads</th><th>Known</th><th>Tokens</th></tr></thead><tbody>{projects}</tbody></table></article></section>
  <section class=\"ledger\"><div class=\"section-head\"><div><h2>Recent threads</h2><p>Thread IDs and deterministic product attribution only. No prompt or response text is rendered.</p></div><span class=\"badge\">READ ONLY</span></div><table><thead><tr><th>Thread</th><th>Product</th><th>Status</th><th>Tokens</th><th>Last event</th></tr></thead><tbody>{thread_rows}</tbody></table></section>
</main>"""
    return page("Token Counter", body)


def page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{escape(title)}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f2f0eb;color:#18201e;font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1280px;margin:auto;padding:48px 42px 72px}}header{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1px solid #c9c8bf;padding-bottom:30px}}.eyebrow{{font:600 11px ui-monospace,monospace;letter-spacing:.13em;color:#66726d;margin:0 0 10px}}h1{{font-size:52px;letter-spacing:-.06em;line-height:.95;margin:0}}h2{{font-size:15px;letter-spacing:-.01em;margin:0 0 21px}}.sub,.section-head p,.muted{{color:#62706a;margin:12px 0 0;font-size:14px}}.stamp{{font:12px ui-monospace,monospace;color:#66726d;text-align:right;line-height:1.7}}.stamp b{{color:#26332e;font-weight:500}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#c9c8bf;border:1px solid #c9c8bf;margin:28px 0}}.metrics div{{background:#f2f0eb;padding:21px 20px}}.metrics span{{display:block;color:#66726d;font-size:12px;margin-bottom:8px}}.metrics strong{{font-size:26px;letter-spacing:-.04em}}.grid{{display:grid;grid-template-columns:1fr 1.35fr;gap:28px;margin-bottom:28px}}article,.ledger{{background:#fbfaf7;border:1px solid #d6d4cb;padding:24px}}.bars{{display:grid;gap:12px}}.day{{display:grid;grid-template-columns:38px 1fr 58px;align-items:center;gap:10px;font:12px ui-monospace,monospace;color:#56635e}}.day i{{height:9px;background:#2e7060;width:var(--w)}}.day b{{text-align:right;color:#23302b;font-weight:500}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{text-align:left;color:#6a746f;font-weight:500;font-size:11px;padding:0 0 10px;border-bottom:1px solid #dedcd4}}td{{padding:11px 0;border-bottom:1px solid #eceae3}}tr:last-child td{{border-bottom:0}}td:not(:first-child),th:not(:first-child){{text-align:right}}.section-head{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:19px}}.section-head h2{{margin:0}}.badge{{font:600 10px ui-monospace,monospace;letter-spacing:.08em;background:#dbe9df;color:#2e7060;padding:6px 8px}}code{{font:11px ui-monospace,monospace;color:#2e7060}}.status{{font:11px ui-monospace,monospace}}.status.available{{color:#2e7060}}.status.unavailable{{color:#99652e}}.empty{{max-width:680px;padding-top:20vh}}.empty h1{{margin-bottom:18px}}@media(max-width:760px){{main{{padding:28px 18px}}header{{align-items:flex-start;gap:20px;flex-direction:column}}h1{{font-size:41px}}.metrics,.grid{{grid-template-columns:1fr 1fr}}.grid article:last-child{{grid-column:1/-1}}.ledger{{overflow-x:auto}}}}
</style></head><body>{body}</body></html>"""


def serve(state_path: Path, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path not in {"/", "/index.html"}:
                self.send_error(404)
                return
            content = render(read_state(state_path), state_path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Token Counter UI: http://{host}:{port}")
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the private local Token Counter ledger")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--html", action="store_true", help="print the static projection and exit")
    args = parser.parse_args()
    if args.html:
        print(render(read_state(args.state), args.state))
    else:
        serve(args.state, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
