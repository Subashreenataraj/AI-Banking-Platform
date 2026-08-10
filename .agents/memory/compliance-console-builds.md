---
name: Compliance console builds
description: Artifact-specific build inputs required for local production verification.
---

The compliance console's Vite configuration requires both `PORT` and `BASE_PATH`; the managed artifact supplies `PORT=21767` and `BASE_PATH=/`.

**Why:** Running the package build without those environment values fails before Vite transforms the app, even though the managed development workflow is healthy.

**How to apply:** Supply the artifact service values when running standalone production build checks; do not change the routing configuration just to accommodate a local shell invocation.