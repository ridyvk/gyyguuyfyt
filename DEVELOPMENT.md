# Development Branches

This repository is currently split into two practical branches:

- `main`: published GitHub Pages static artifact. Keep this branch stable because GitHub Pages serves it directly.
- `develop`: source branch restored from the latest available React/Vite source tree. Use this branch for app, data pipeline, and workflow development.

## Safe workflow

1. Make source changes on `develop` or a branch created from `develop`.
2. Build and validate there.
3. Publish only the generated static output to `main` after the app has been checked.

Do not replace `main` with experimental source changes unless the GitHub Pages deployment path has been intentionally changed.
