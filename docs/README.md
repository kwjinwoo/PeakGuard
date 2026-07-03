---
id: wiki-home
title: PeakGuard Wiki
type: index
status: active
related:
  - index.md
  - status.md
  - architecture.md
---

# PeakGuard Wiki

This directory is PeakGuard's canonical knowledge base for people and LLM agents. Pages are intentionally small, linked, and independently understandable.

For a complete document catalog, see [Documentation index](index.md).

## Reading order for a new task

1. Read [Current status](status.md) for the verified baseline and active concerns.
2. Read [System overview](architecture.md) for boundaries and data flow.
3. Follow the relevant topic from [Concepts](concepts/README.md).
4. Check [Roadmap](roadmap.md), [Proposals](proposals/README.md), and [Work notes](work-notes/README.md) for unfinished context.
5. Read the relevant [Decision record](decisions/README.md) before changing an established constraint.

## Wiki map

| Area | Purpose |
| --- | --- |
| [Status](status.md) | Short, dated snapshot of what works and what needs attention |
| [Architecture](architecture.md) | System boundaries and daily processing flow |
| [Concepts](concepts/README.md) | Canonical domain and technical knowledge |
| [Operations](operations.md) | Runtime, secrets, persistence, and failure behavior |
| [Roadmap](roadmap.md) | Phase-based development plan and completion checklist |
| [Proposals](proposals/README.md) | Ideas under consideration but not yet accepted |
| [Decisions](decisions/README.md) | Accepted architectural decisions and rationale |
| [Runbooks](runbooks/README.md) | Repeatable responses to operational symptoms |
| [Work notes](work-notes/README.md) | Difficulties encountered while coding or working with an LLM |
| [Wiki meta](meta/README.md) | Writing, growth, frontmatter, and templates |

## Source-of-truth rule

Code and tests define executable behavior. The Wiki explains intent, invariants, relationships, operational knowledge, and future direction. When they disagree, verify the implementation and tests, record the discrepancy in a work note, and update the stale document in the same change.
