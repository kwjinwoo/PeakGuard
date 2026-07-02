---
name: peakguard-wiki
description: Read, navigate, create, update, split, and validate the repository-local PeakGuard LLM Wiki under docs/. Use for any task that asks Codex to consult project status or documentation, record project knowledge or work difficulties, update roadmap/proposals/ADRs/runbooks, maintain Wiki frontmatter or indexes, or repair documentation links and structure.
---

# PeakGuard Wiki

Treat `docs/` as the project's durable memory. Keep executable claims aligned with code and tests, and keep navigation valid for both people and LLM agents.

## Choose a workflow

- For questions or context gathering, use **Read the Wiki** and do not modify files.
- For documentation creation, correction, reorganization, or recording learned context, use **Write the Wiki**.
- For a Wiki integrity check, run **Validate the Wiki** without changing content unless the user asked for fixes.

## Read the Wiki

1. Start at `docs/index.md` to locate knowledge by document type.
2. Read `docs/status.md` for the last verified baseline and known concerns.
3. Read only the relevant concept, operation, roadmap, proposal, decision, runbook, or work-note pages.
4. Follow frontmatter `related` edges and body links when more context is needed.
5. Inspect frontmatter `code` and `tests` paths before relying on behavioral claims.
6. When documentation and implementation differ, treat code plus tests as executable evidence, state the discrepancy, and avoid silently presenting stale documentation as fact.

Return the smallest sufficient context. Do not load the entire Wiki when a focused traversal answers the task.

## Write the Wiki

### Place knowledge by purpose

- Current verified baseline: `docs/status.md`.
- Current domain or technical knowledge: `docs/concepts/`.
- Runtime and secret handling: `docs/operations.md`.
- Near- and long-term direction: `docs/roadmap/`.
- Unaccepted design ideas: `docs/proposals/`.
- Accepted architectural rationale: `docs/decisions/`.
- Repeatable operational recovery: `docs/runbooks/`.
- Reusable difficulties encountered while coding or working with an LLM: monthly `docs/work-notes/YYYY-MM.md`.

Do not record routine typos, every failed command, or transient task status as work notes.

### Maintain frontmatter

Give every Wiki Markdown file except `docs/AGENTS.md` these fields:

- `id`: unique stable identifier that survives file moves.
- `title`: human-readable title.
- `type`: one of `index`, `status`, `architecture`, `operations`, `concept`, `reference`, `roadmap`, `proposal`, `decision`, `runbook`, `work-note`, `meta`, or `template`.
- `status`: one of `active`, `proposed`, `accepted`, `archived`, or `superseded`.

Add only relevant optional fields:

- `related`: Wiki paths relative to the current document.
- `code` and `tests`: paths relative to the repository root.
- `created`: creation date for proposals and decisions.
- `last_verified`: date behavioral claims were checked against implementation and tests.
- `verified_by`: commands used to establish a status snapshot.

Keep frontmatter small. Explain relationship meaning in the body rather than inventing more metadata fields.

### Keep pages focused

Make one page answer one primary question. Split a page when it exceeds roughly 300 lines or 20 KB, contains three independently searchable topics, regularly needs heading level four or deeper, or changes for unrelated reasons.

When splitting:

1. Identify stable knowledge units rather than cutting by length.
2. Keep the old page as an overview and navigation hub when possible.
3. Put detailed pages in a same-named directory.
4. Update the hub, parent indexes, frontmatter relationships, and body links.
5. Search the repository for stale paths.

### Complete every write

1. Add every durable page to `docs/index.md` and its nearest directory index.
2. Update `docs/status.md` only when verified project state changed.
3. Preserve ADRs, resolved proposals, and useful work notes; mark them archived or superseded instead of deleting history.
4. Promote repeated work-note knowledge into a concept, runbook, proposal, or ADR and link the original note.
5. Use templates under `docs/meta/templates/` when creating proposals, decisions, or monthly work-note files.
6. Run the bundled validator and fix every reported error.

## Validate the Wiki

From the repository root, run:

```bash
uv run python .agents/skills/peakguard-wiki/scripts/validate_wiki.py
```

The validator checks required frontmatter, allowed values, unique IDs, `related` paths, code/test paths, Markdown links, deprecated Wiki files, and complete `docs/index.md` coverage.

After a Wiki write, also run `uv run pre-commit run --all-files`. Run project tests when documentation claims, status, or code behavior changed; documentation-only navigation edits do not require tests unless repository policy says otherwise.
