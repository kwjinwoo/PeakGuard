---
id: concepts-index
title: Concepts
type: index
status: active
related:
  - domain-model.md
  - configuration.md
  - data-contracts.md
  - portfolio-context.md
  - portfolio-actions.md
  - review-levels.md
  - alerts/README.md
---

# Concepts

These pages contain canonical, current-state knowledge about PeakGuard.

- [Domain model](domain-model.md): price history, rolling ATH, MDD, and alert semantics.
- [Configuration](configuration.md): `portfolio.yaml` contract and validation.
- [Data contracts](data-contracts.md): persisted CSV and integration-facing data shapes.
- [PortfoTrack allocation context](portfolio-context.md): optional local schema 1.0 export and validation.
- [Portfolio actions](portfolio-actions.md): allocation guidance classification and precedence.
- [Discount review levels](review-levels.md): MDD, Z-score, bounce, and thesis precedence.
- [Alert catalog](alerts/README.md): alert inputs, conditions, and output behavior.
- [Testing strategy](testing-strategy.md): test boundaries and external isolation.
- [Glossary](glossary.md): canonical project terminology.

When a concept page becomes too large, use the repository-local `$peakguard-wiki` skill to retain it as a navigation hub and move independently retrievable topics into a same-named subdirectory.
