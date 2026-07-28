# Ledger progress

- Task 0 complete (2026-07-28): source counts verified: Claude 106 directories; Codex 889 JSONL files (within the stated tolerance).
- Goal: build a standard-library, reproducible local cost ledger by project and channel, with explicit unclassified coverage.
- Order: lock Codex final-cumulative extraction; collect Claude; assign each source key once; report and gaps; fixture tests plus mutation proof.
- Maximum risk: Codex `total_token_usage` is cumulative, so summing JSONL events silently inflates spend; collection must retain only each file's final usable total.
- Task 1 complete: `collect` emits normalized Claude events and exactly one Codex record per scanned JSONL, retaining only the file's final cumulative usage. Acceptance output: `889 106`.
- Task 2 complete: conservative longest-prefix attribution assigns every normalized record once; all unmatched sources go to `未归类`. Invariant acceptance output: `INVARIANT OK 1920872`.
- Task 3 complete: human report now prints project, Claude, Codex, and total columns, renders zero amounts as `无日志`, and ends with the no-log count plus `未归类` amount share. Tail acceptance includes both required terms.
- Task 4 complete: three fixture-only tests cover final Codex cumulative extraction, longest-prefix no-loss attribution, and `未归类` fallback. Mutation proof: changing Codex extraction to sum produced `AssertionError: 90 != 60`; restoring final-only extraction produced `Ran 3 tests ... OK`.
- Final verification complete: fresh full scan printed `INVARIANT OK 1920912`; fixture suite printed `Ran 3 tests ... OK`; protected-path diff with explicit `--` was empty and exited 0. The strict unseparated protected-file command remains blocked only because both specified files are absent, as recorded in `BLOCKED.md`.
