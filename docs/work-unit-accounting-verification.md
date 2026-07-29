# Work Unit accounting verification

This record documents a read-only verification of the two history formats on
2026-07-29. It contains paths, timestamps, and token counters only; no prompt
or assistant body was copied.

## Codex cumulative snapshot delta

Source: `~/.codex/sessions/2026/07/29/rollout-2026-07-29T11-01-32-019fabd1-f79d-7d11-94de-83d26e397661.jsonl`.

Window: `03:10:45Z` to `03:11:35Z`. The parser found the last snapshot before
the start at `03:10:43.712Z` and the final snapshot before the end at
`03:11:34.640Z` (39 snapshots total).

| Field | Start cumulative | End cumulative | Work Unit delta |
| --- | ---: | ---: | ---: |
| Fresh input (`input - min(cached, input)`) | 148,410 | 164,910 | 16,500 |
| Cached input | 2,460,928 | 3,206,656 | 745,728 |
| Output | 21,721 | 23,629 | 1,908 |
| Total | — | — | 764,136 |

The total is `16,500 + 745,728 + 1,908`, not a sum of the cumulative records.
Codex cache-write is recorded as unavailable even when the raw format presents
a zero-valued compatibility field.

## Claude per-message usage sum

Source: `~/.claude/projects/-Users-wendy-Documents-----/a6c62f3a-5e8f-4cc7-89be-76715bf854e3.jsonl`.

Window: `03:09:00Z` to `03:11:30Z`. The parser found two unique assistant
message IDs carrying usage. The session had two duplicate serialized copies of
those IDs, which were suppressed before summing.

| Field | Work Unit delta |
| --- | ---: |
| Input | 4 |
| Cache read | 1,162,617 |
| Cache write | 7,032 |
| Output | 5,408 |
| Total | 1,175,061 |

The Claude value is the sum of delta `message.usage` fields inside the window,
not a cumulative-difference calculation.

## Runtime invariant

The lifecycle hook calls `collect_accounting` only after a transition to
`done` or `blocked`. The running record therefore contains a start timestamp
and no `token_accounting`; missing or not-yet-flushed history becomes an
explicit unavailable accounting result with no retry or polling loop.
