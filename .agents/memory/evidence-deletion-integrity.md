---
name: Evidence deletion integrity
description: The consistency rule for removing indexed compliance evidence.
---

Document deletion is a two-store operation: remove the source metadata/file and all vector chunks keyed to that document. Do not delete the database row first if vector cleanup can fail.

**Why:** A stale Chroma chunk can continue to appear in grounded answers after the source document is gone, undermining auditability and evidence-backed claims.

**How to apply:** Keep vector cleanup in the normal document-delete path, fail safely before metadata deletion when cleanup fails, and verify retrieval cannot return deleted source IDs.