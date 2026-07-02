---
id: work-notes-index
title: Work Notes
type: index
status: active
related:
  - 2026-07.md
  - ../runbooks/README.md
  - ../meta/README.md
---

# Work Notes

Work notes preserve difficulties encountered while coding or during LLM-assisted work so a future task does not repeat the same investigation.

## What to record

Record a note when the difficulty:

- consumed meaningful investigation time;
- exposed a mismatch between documentation, code, tests, or assumptions;
- is likely to recur for another maintainer or agent; or
- produced a reusable verification technique.

Do not record routine typos, obvious failed commands, status tracking, or every implementation step.

## Format and storage

Use one monthly file named `YYYY-MM.md`. Add newest entries at the top using the template in `../meta/templates/work-note.md`. Keep entries concise: context, difficulty, verification, conclusion, and related links.

When a note becomes durable knowledge, promote it to a concept, runbook, proposal, or ADR. Keep the original note and add a link to the promoted document.

## Index

- [2026-07](2026-07.md)
