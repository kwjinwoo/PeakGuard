---
id: ADR-0001
title: Persist Rolling History as CSV in a GitHub Gist
type: decision
status: accepted
created: 2026-07-02
related:
  - ../concepts/data-contracts.md
  - ../operations.md
code:
  - src/peakguard/storage.py
  - src/peakguard/gist_client.py
tests:
  - tests/test_storage.py
  - tests/test_gist_client.py
---

# ADR-0001: Persist rolling history as CSV in a GitHub Gist

- Status: Accepted
- Date: 2026-07-02

## Context

PeakGuard needs durable daily closing-price history for a small portfolio while preserving zero-cost, serverless operation. The data should be inspectable and editable without provisioning a database.

## Decision

Persist rolling history in a GitHub Gist file named `peak_prices.csv`. Each row contains `ticker,date,price`. `peakguard.storage` owns deterministic serialization, while `peakguard.gist_client` owns remote transport.

## Consequences

- Production requires `GIST_PAT` and `GIST_ID` secrets.
- The data remains human-readable and portable.
- Each run reads and rewrites the small dataset as one document.
- Concurrent writers and large datasets are outside the supported design.
- Schema changes require coordinated serializer, parser, test, and documentation updates.

## Alternatives considered

- JSON in a Gist: workable, but no longer matches the row-oriented history implementation.
- Repository commits: creates noisy automated history and requires write permissions to repository contents.
- SQL or managed databases: add cost and operational complexity disproportionate to the dataset.
