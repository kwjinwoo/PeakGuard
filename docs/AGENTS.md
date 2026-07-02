# Documentation Guide

This directory is PeakGuard's canonical project wiki for both people and LLM agents. Keep pages factual, compact, easy to retrieve independently, and synchronized with the code.

## Writing rules

- Give each page one primary topic and a descriptive filename.
- Begin with a short purpose statement and link related pages explicitly.
- Prefer concrete names, paths, schemas, commands, invariants, and examples over narrative background.
- State current behavior in present tense. Put rejected or historical alternatives in an ADR instead of mixing them into current guidance.
- Do not duplicate detailed rules across pages. Choose one canonical page and link to it.
- Never include credentials, tokens, chat IDs, Gist IDs, or copied production data.
- Use repository-relative Markdown links so the wiki works on GitHub and locally.

## Maintenance rules

- Update the relevant wiki page in the same change as architecture, persistence format, configuration schema, alert semantics, or operational workflow changes.
- Add a short ADR under `decisions/` for decisions that constrain future design or replace an established approach.
- Keep `README.md` as the navigation hub and add every durable page to its index.
- Use the repository-local `$peakguard-wiki` skill for Wiki reading, writing, restructuring, and validation.
- Add every durable Wiki page to `index.md` and give it valid frontmatter.
- Reference source files rather than embedding large code excerpts that will drift.
- Verify commands against `pyproject.toml`, workflow files, and the current package layout before documenting them.
- At the start of substantial work, read `status.md`, the relevant concept pages, and linked decisions or work notes.
- At the end of substantial work, update `status.md` only if the verified project state changed. Record reusable difficulties in the current monthly `work-notes` file.
- Follow the `$peakguard-wiki` write workflow when adding, splitting, moving, or retiring pages.
