# Local secrets

Real credentials never belong in chat messages, shell arguments, YAML configuration, Git history, run manifests, logs, notebooks, or screenshots.

For local development:

1. Copy `.env.example` to `.env`.
2. Put the value after the matching variable name in `.env`.
3. Keep the variable name in committed configuration; read its value through `require_secret` only inside the adapter that needs it.

The repository ignores `.env` and CI verifies that generated data is excluded. Operating-system or CI environment variables take precedence over `.env`, allowing later migration to GitHub Actions Secrets or a managed secret store without changing research configuration.

BaoStock does not require a key. Tushare and AmazingData adapters will fail with a clear missing-secret error before making a request, and diagnostics expose only whether a variable is configured.

