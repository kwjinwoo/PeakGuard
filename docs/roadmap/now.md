---
id: roadmap-now
title: Now
type: roadmap
status: active
related:
  - README.md
  - ../proposals/PROP-0001-distinguish-gist-read-failures.md
---

# Now

## Establish the Wiki as the shared project memory

- Keep current behavior, future ideas, decisions, runbooks, and work notes distinct.
- Ensure all durable documents are reachable from `docs/README.md` or a directory index.
- Update documentation alongside behavior changes.

## Make Gist read failure semantics explicit

The current orchestrator treats every `GistError` as an empty first run. Decide and implement how missing files, authentication failures, rate limits, and transient network failures differ before expanding persistence behavior.

Related: [PROP-0001](../proposals/PROP-0001-distinguish-gist-read-failures.md).
