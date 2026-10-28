# certifi security update: GHSA-6q48-6c7w-9gw2

This change pins certifi 2026.10.19 in Poetry and requirements.txt. The
official advisory recommends 2026.10.19 or later:
https://github.com/advisories/GHSA-6q48-6c7w-9gw2

The installed wheel was checked against its PyPI SHA-256, and its PEM bundle
was parsed to verify that `emSign ECC Root CA - G3` is absent. Other locked
package versions are unchanged. certifi is used by httpx, httpcore and requests;
their existing dependency constraints accept this version.

## Deployment impact

- `railway.json` builds the backend using the root Dockerfile.
- The Dockerfile installs from poetry.lock: existing images must be rebuilt.
  Poetry is pinned to the lock generator's version (1.8.3). Dependencies are
  installed before copying source, and the project is installed afterward with
  its README available. This avoids installing the project before it exists.
- `.github/workflows/fly-deploy.yml` deploys on pushes to main. Review this
  automatic deployment before merging; opening this PR does not trigger it.
  No fly.toml is tracked, and no Actions runs were returned during review.
- The deployment guide describes Railway/Vercel and local Cloudflare tunnels;
  these files do not establish which backend is currently running.
- docker-compose.yml references an absent Dockerfile.backend. Confirm the
  actual deployment path before using Compose.
- requirements.txt already differs from the full Poetry dependency set. This
  security change updates its certifi pin without regenerating unrelated pins.

## Validation performed

- Poetry dependency resolution and installation on Python 3.12 succeeded.
- `poetry check --lock` and `python -m pip check` succeeded.
- `tests/security/test_certifi_trust.py`: 3 passed.
- HTTPX verified SSL-context creation and OpenAI client initialization passed
  without outbound API requests.
- Existing `tests/llm/test_sql_generator_fixed.py`: 13 passed, 5 failed. The
  same five failures reproduced on unmodified main source using the same test
  environment (initialization defaults, prompt, model choice, generation and
  cache expectations). These are not a passing full-suite result.
- No Docker executable was available, so container build and startup have not
  been verified. No production services were changed.
- The local runner preloads a G3 root into new SSL contexts independently of
  certifi. The regression test therefore parses the bundle itself. Runtime
  trust overrides must also be checked in the real deployment.

## Remaining rollout steps

1. Identify the live backend, its deployed commit/image, Python environment,
   replicas/workers, deployment triggers and rollback image. Confirm impact
   before merging or deploying.
2. Build a candidate image from this PR, without restarting production:
   `docker build --pull --no-cache -t sens:certifi-2026.10.19 .`
3. In the candidate and later each deployed runtime, check the actual version
   and bundle path with
   `python -c 'import certifi; print(certifi.__version__, certifi.where())'`.
   Run the security regression tests in a test environment. Check custom CA
   files, SSL_CERT_FILE, SSL_CERT_DIR, REQUESTS_CA_BUNDLE and any vendored CA
   bundles (including tooling such as pip); updating application certifi does
   not update every independent trust store.
4. Validate startup, `/health`, database/Redis access and verified HTTPS to the
   configured LLM and data services in staging. Do not disable TLS verification.
5. After deployment impact is confirmed, roll out the rebuilt image, restart
   all affected processes and repeat runtime/version/health checks. A rollback
   to the old image would reintroduce the affected bundle.
6. Recheck Dependabot alerts #594 and #595 after merge. Their current status
   could not be read through the available GitHub connector; they have not
   been dismissed or asserted resolved.
