# Loom script: AI Voice Operator (under 3 min)

Screen recording with your face bubble on. Founders decide in the first 20 seconds.

| Time | Show | Say |
|---|---|---|
| 0:00–0:15 | Dashboard tiles | "This AI receptionist answers calls and WhatsApp, qualifies leads and books meetings. Live calls cost $X versus about $7 for a human SDR. Let me call it." |
| 0:15–1:15 | Phone on speaker. Call the Twilio number and play a good lead. | Give a budget, say you're the decision maker, give a 2-week timeline. Ava offers slots and the SMS arrives. Hold it up to the camera. |
| 1:15–1:35 | Refresh the dashboard: new row, `booked`. Open the HubSpot contact, status Open Deal. | "The lead is in the CRM and no human touched it." |
| 1:35–1:55 | WhatsApp: "hi, budget is $300/mo" | The bot politely disqualifies. "Low-budget leads don't eat your calendar." |
| 1:55–2:30 | `qualify.py` and `test_qualify.py` | "The LLM only extracts facts. Deterministic, tested code decides who qualifies, so a prompt change can't book bad leads." |
| 2:30–2:50 | `simulate_calls --n 800` output, then `/metrics` | "Load-tested with 800 conversations through the real pipeline. p95 tool latency is X ms. Simulated data is kept separate from live data." |
| 2:50–3:00 | Your face | "I can set this up for your business in a week. Booking link below." |

**Before recording:** get 20+ real calls into the database (friends, family, yourself with different scripts) so the live column isn't empty.
