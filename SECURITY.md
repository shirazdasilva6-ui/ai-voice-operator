# Security

## Reporting a vulnerability

Please don't open a public issue. Use GitHub's **Report a vulnerability** button (Security tab) or email the maintainer listed on the profile.

## What's protected, and how

| Surface | Protection | Where |
|---|---|---|
| Vapi webhook | Shared secret (`x-vapi-secret`), compared in constant time | `app/security.py`, `routes/vapi.py` |
| WhatsApp webhook | Twilio request signature | `integrations/twilio_client.py` |
| Stripe webhook | Stripe signature on the raw body | `routes/billing.py` |
| `/metrics`, `/calls`, `/vapi/assistant-config` | Bearer `DASHBOARD_TOKEN`; the dashboard sends it server-side, never to the browser | `app/security.py`, `web/app/page.tsx` |
| Misconfiguration | `APP_ENV=production` **refuses to start** if any of the above secrets is missing, or if Stripe is on without what auto-setup needs (`VAPI_API_KEY`, `TWILIO_ACCOUNT_SID`) | `config.production_problems()` |
| Information leaks | API docs off in production; tool errors never pass internal details to the LLM (which could speak them to a caller); phone numbers masked in `/calls` | `main.py`, `agent/tools.py`, `routes/metrics.py` |
| SQL injection | Values are always parameterized; the only interpolated identifiers come from an allowlist | `db.py` |
| Prompt injection | The LLM only extracts facts; booking is decided by tested code that checks DB state | `agent/qualify.py`, `agent/tools.py` |
| Containers | API and web run as unprivileged users; `.dockerignore` keeps `.env` and build junk out of image layers | `api/Dockerfile`, `web/Dockerfile`, `*/.dockerignore` |
| Dependencies | `npm audit` / `pip-audit` clean as of 2026-10-28; Dependabot weekly | `.github/dependabot.yml` |

All of the above is covered by `api/tests/test_security.py`.

## Auto-provisioning (spends real money)

A paid checkout buys a Twilio number and creates a Vapi assistant, so this path gets its own guards:

| Risk | Protection | Where |
|---|---|---|
| Buying numbers before the client's money arrives | Only provision when `payment_status` is `paid`/`no_payment_required`; delayed bank payments wait for `async_payment_succeeded` | `routes/billing.py` (`should_provision`) |
| Two runs for one client (Stripe retries) | Atomic `claim()`: only one run can move a client into `provisioning` | `provisioning.claim()` |
| A crash strands a paying client | Each step is saved before the next; a run older than 15 min can be reclaimed | `provisioning.claim()` |
| A crash leads to a second number being bought | Numbers are tagged `vo-<customer id>` in Twilio and reused on retry | `provisioning.buy_number()` |
| Client-typed business names injecting HTML into emails | Escaped before going into email HTML; error text too | `provisioning.onboarding_html()` |
| SQL via column names | `save()` only accepts allowlisted columns | `provisioning.save()` |

Covered by `api/tests/test_provisioning.py` and `test_provisioning_db.py` (the latter against real Postgres in CI).

**Known trade-off:** Vapi needs the Twilio account SID and auth token to attach numbers, so the auth token is shared with Vapi. A Twilio sub-account per client would limit that exposure; it's on the roadmap.

## Known limitations

- **Local-only DB password.** `docker-compose.yml` uses `postgres/postgres`. The DB port isn't published, and production uses Supabase credentials from the environment.
- **No rate limiting yet** on the webhooks. They're authenticated, so only Vapi, Twilio and Stripe can reach the paid code paths.
