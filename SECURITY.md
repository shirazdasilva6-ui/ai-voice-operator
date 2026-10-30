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
| Misconfiguration | `APP_ENV=production` **refuses to start** if any of the above secrets is missing | `config.production_problems()` |
| Information leaks | API docs off in production; tool errors never pass internal details to the LLM (which could speak them to a caller); phone numbers masked in `/calls` | `main.py`, `agent/tools.py`, `routes/metrics.py` |
| SQL injection | Values are always parameterized; the only interpolated identifiers come from an allowlist | `db.py` |
| Prompt injection | The LLM only extracts facts; booking is decided by tested code that checks DB state | `agent/qualify.py`, `agent/tools.py` |
| Containers | API and web run as unprivileged users; `.dockerignore` keeps `.env` and build junk out of image layers | `api/Dockerfile`, `web/Dockerfile`, `*/.dockerignore` |
| Dependencies | `npm audit` / `pip-audit` clean as of 2026-10-28; Dependabot weekly | `.github/dependabot.yml` |

All of the above is covered by `api/tests/test_security.py`.

## Known limitations

- **Local-only DB password.** `docker-compose.yml` uses `postgres/postgres`. The DB port isn't published, and production uses Supabase credentials from the environment.
- **No rate limiting yet** on the webhooks. They're authenticated, so only Vapi, Twilio and Stripe can reach the paid code paths.
