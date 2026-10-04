> Created: 2026-05-28 · Updated: 2026-05-28 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Expose webhook via ngrok + wire up TradingView

## Context

Webhook bot is running on `localhost:8000` and Telegram delivery is confirmed.
TradingView webhooks require a **public HTTPS URL** — it cannot reach localhost.
Goal: install ngrok, tunnel port 8000, get a public URL, and configure a
TradingView alert to call it. No code changes to the bot itself.

## Steps

### 1 — Install ngrok

Download the Windows zip from https://ngrok.com/download (no account needed for
basic use), extract `ngrok.exe` to any folder on your PATH — or just place it in
the webhook project folder.

Alternatively, with Chocolatey (if installed):
```powershell
choco install ngrok -y
```
Or with winget:
```powershell
winget install ngrok.ngrok
```

### 2 — Start the tunnel (leave uvicorn running)

Open a **new** PowerShell window and run:
```powershell
ngrok http 8000
```

ngrok will print a forwarding URL like:
```
Forwarding   https://a1b2c3d4.ngrok-free.app -> http://localhost:8000
```
Copy that `https://...ngrok-free.app` URL.

### 3 — Verify the tunnel reaches the bot

In a third PowerShell window:
```powershell
Invoke-RestMethod -Uri "https://<YOUR_NGROK_URL>/health"
# Expected: {"status":"ok","service":"TradingView Telegram Webhook"}
```

### 4 — Configure TradingView alert

In TradingView → Alerts → Create Alert:

**Webhook URL** (in "Notifications" tab → "Webhook URL"):
```
https://<YOUR_NGROK_URL>/tv-webhook
```

**Alert Message** (in "Settings" tab → "Message" box — paste exactly):
```json
{
  "passphrase": "<YOUR_SECURITY_PASSPHRASE>",
  "ticker":     "{{ticker}}",
  "price":      "{{close}}",
  "timeframe":  "{{interval}}",
  "stage":      "1D CRTL Sweep / Liquidity Test"
}
```
Replace `<YOUR_SECURITY_PASSPHRASE>` with the value in your `.env`.

### 5 — Verify end-to-end

Once the alert fires (or trigger it manually from TradingView), confirm:
- uvicorn terminal shows `Incoming payload: {...}` and `Telegram message sent successfully`
- Telegram card arrives in your chat

## Notes

- **ngrok URL changes each restart** — free tier issues a new URL every time
  ngrok is restarted. Update the TradingView webhook URL whenever you restart.
- **Production fix**: deploy to a VPS with a fixed domain (next step after this).
- The webhook bot code needs no changes for this step.

---

### 1 — Send a valid test alert

Open a **new** PowerShell window (leave uvicorn running in the other one) and run:

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/tv-webhook" `
  -ContentType "application/json" `
  -Body '{
    "passphrase": "<YOUR_SECURITY_PASSPHRASE>",
    "ticker":    "GBPCAD",
    "price":     "1.74823",
    "timeframe": "1D",
    "stage":     "1D CRTL Sweep / Liquidity Test"
  }'
```

Replace `<YOUR_SECURITY_PASSPHRASE>` with the value from your `.env`.

**Expected response (HTTP 200):**
```json
{"status": "ok", "message": "Alert processed"}
```

**Expected Telegram card:**
```
🎯 Market Stage Triggered
━━━━━━━━━━━━━━━━━━━━━
• Asset:      GBPCAD
• Structure:  1D CRTL Sweep / Liquidity Test
• Price:      1.74823
• Timeframe:  1D
• Time:       <UTC timestamp>
━━━━━━━━━━━━━━━━━━━━━
⚠️ Check charts for structural rejection or breakout confirmation.
```

### 2 — Confirm Telegram card arrived

Open your Telegram channel/group. The card should appear within a few seconds.

### 3 — Test bad passphrase → 401

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/tv-webhook" `
  -ContentType "application/json" `
  -Body '{"passphrase": "wrongpassword", "ticker": "GBPCAD", "price": "1.0", "timeframe": "1D", "stage": "test"}'
```

Expected: HTTP 401 — `{"detail": "Unauthorized"}` — no Telegram card.

## No code changes

Everything is already wired. This is a pure run-and-observe test.

Resolution agreed with the user:
- **Testing needs no exchange keys.** Freqtrade dry-run uses only public market
  data; the bridge itself only needs the freqtrade REST API.
- To avoid running/trusting freqtrade's code at all during *our* integration
  test, we'll point the webhook at a **throwaway local mock** of freqtrade's
  `/api/v1/forceenter`. This fully exercises our code path (basic auth, payload,
  response handling) with zero exchange exposure.
- The user **will provide real Telegram credentials** so the full chain
  (Telegram alert card + freqtrade trigger) is tested exactly as in production.
  (No code change to decouple Telegram — keep alert-first behaviour.)
- Real freqtrade + live exchange keys is a **separate later step**, documented
  with safety practices, not part of this test.

## Already done (prior step, verified with stubbed HTTP)

- `fastapi-webhook-bot\fastapi-webhook-bot\main.py` — `AUTONOMOUS_MODE` +
  `FREQTRADE_API_*` config, `trigger_freqtrade_entry()` helper
  (`POST {FREQTRADE_API_URL}/api/v1/forceenter`, basic auth), and the autonomous
  branch in `/tv-webhook`.
- `.env.example` — documents the four new vars.
- `freqtrade-crth-strategy\...\config.json` — `api_server.enabled: true`,
  `force_entry_enable: true` (creds still placeholders).
- `D:\TradeAnalyseOpenSource\CLAUDE.md` — single root doc.

## Work to do

### 1. Throwaway local mock freqtrade API (test-only, NOT committed)

Create a tiny FastAPI app in a temp dir (outside the repo) exposing
`POST /api/v1/forceenter` that:
- requires HTTP basic auth (a known test username/password),
- echoes the received JSON body and returns a freqtrade-like trade confirmation,
- records the call so we can assert auth + payload were correct.
Run it on `localhost:8080` in the temp venv already used for verification.

### 2. Run the webhook bot against the mock + real Telegram

- Env at runtime only (not persisted to any committed file):
  `AUTONOMOUS_MODE=true`, `FREQTRADE_API_URL=http://localhost:8080`,
  `FREQTRADE_API_USERNAME`/`FREQTRADE_API_PASSWORD` matching the mock,
  `SECURITY_PASSPHRASE`, and the user-provided `TELEGRAM_BOT_TOKEN` +
  `TELEGRAM_CHAT_ID`.
- Start `uvicorn main:app --port 8000`.

### 3. Fire a real test alert and assert the full chain

`POST /tv-webhook` with `{passphrase, ticker, price, timeframe, stage,
pair: "BTC/USDT"}` and confirm:
- HTTP 200 with an `autonomous` block in the response,
- a **real Telegram card** arrives in the user's chat,
- the mock received the `forceenter` call with correct basic auth and
  `{"pair": "BTC/USDT", "side": "long"}`,
- a bad passphrase still returns 401 and never reaches the mock.

### 4. Add exchange-key security guidance to `CLAUDE.md`

Append a short "Going live safely (exchange API keys)" section:
- dry-run needs no keys;
- when going live, create the exchange key with **withdrawals disabled** and
  **IP-whitelisted**;
- keys stay local in `config.json`, sent only to the exchange over HTTPS;
- never commit real keys; keep `dry_run: true` until intentionally live.

## Out of scope (later, user-initiated)

- Installing/running real freqtrade (Docker image, dry-run) to confirm the live
  contract — deferred; the documented API contract + mock test cover our code.
- Any real exchange keys.

## Verification

- Mock receives exactly one `forceenter` call per valid alert, with correct
  auth + body; webhook response contains the `autonomous` block.
- User confirms the Telegram card actually arrived in their chat.
- Bad passphrase → 401, no mock call.
- Re-read `CLAUDE.md` to confirm the new security section is accurate and no real
  secrets were written anywhere. Tear down the temp venv/mock afterward.

---

# Follow-up: load `.env` for local runs (approved)

## Context

`main.py` reads config via `os.getenv(...)`, which only reads the process
environment. Docker works because `docker-compose.yml` uses `env_file: .env`,
but a local `uvicorn main:app` ignores the `.env` entirely — `main.py` never
calls `load_dotenv()`, even though `python-dotenv` is already in
`requirements.txt`. The user filled in a real `.env` and wants local runs to
fetch those values automatically.

## Change

`fastapi-webhook-bot/fastapi-webhook-bot/main.py` — add two lines so the `.env`
is loaded before the config block reads it:
- `from dotenv import load_dotenv` (with the other imports near the top)
- `load_dotenv()` called immediately after imports, **before** the
  `os.getenv(...)` configuration block (lines ~21-31).

No other files change. `python-dotenv==1.0.1` is already declared, so no new
dependency. Docker behaviour is unaffected (env_file still wins / coexists).

## Also: clarify the two self-chosen secrets in `.env.example`

The user was unsure how to obtain `SECURITY_PASSPHRASE` and
`FREQTRADE_API_PASSWORD`. Neither is fetched from an external service — both are
secrets the user invents and must keep consistent across two places. Tighten the
comments in `fastapi-webhook-bot/fastapi-webhook-bot/.env.example`:
- `SECURITY_PASSPHRASE` — "Invent any strong string; put the SAME value in your
  TradingView alert JSON `passphrase` field."
- `FREQTRADE_API_USERNAME` / `FREQTRADE_API_PASSWORD` — "Must match freqtrade
  config.json `api_server.username` / `password`."

Blank lines like `SECURITY_PASSPHRASE=` and `FREQTRADE_API_PASSWORD=` resolve to
**empty strings** once loaded (overriding the in-code defaults), so they must be
filled in for auth to work.

## Verification

- From the project dir, `uvicorn main:app --port 8000` (no `--env-file`); confirm
  the app picks up `.env` values (e.g. a request authenticates against the
  `SECURITY_PASSPHRASE` set in `.env`, not the code default).
- Do not print `.env` contents during verification (per the CLAUDE.md rule);
  assert behaviour via endpoint responses only.

---

# Follow-up: persist a "Secrets setup" step-by-step guide (approved-pending)

## Context

The user repeatedly asked how to obtain `SECURITY_PASSPHRASE` and
`FREQTRADE_API_PASSWORD`. They are self-generated secrets (not fetched from any
service); the confusion is worth fixing permanently with an explicit, copy-paste
setup guide in the repo rather than only in chat.

## Change

Add a **"## Secrets setup (step by step)"** section to the webhook bot README
`fastapi-webhook-bot/fastapi-webhook-bot/README.md` (right after the existing
"Configuration" section), containing:

1. **SECURITY_PASSPHRASE** — generate with
   `python -c "import secrets; print(secrets.token_urlsafe(24))"`; put in `.env`;
   mirror the SAME string in the TradingView alert JSON `passphrase` field.
2. **FREQTRADE_API_USERNAME / PASSWORD** — set in freqtrade `config.json`
   `api_server` (username/password, plus regenerate `jwt_secret_key` via
   `token_hex(32)` and `ws_token` via `token_urlsafe(32)`), then copy the same
   username/password into `.env`. Restart both services.
3. **Verify** the freqtrade creds with
   `curl -u <user>:<pass> http://localhost:8080/api/v1/ping` → expect
   `{"status":"pong"}`, wrong creds → 401.

4. **Restart so changes load (user chose LOCAL uvicorn):**
   - Primary: in the uvicorn terminal press Ctrl+C, then re-run
     `uvicorn main:app --port 8000` (`load_dotenv()` reads `.env` only at startup;
     `--reload` does not re-read it).
   - Free port 8000 first if a container is running: `docker compose down`.
   - (Secondary note) Docker alternative: `docker compose up -d --force-recreate`;
     container name is `tv-telegram-webhook`. Don't run both at once.
   - Freqtrade (when running): `docker restart <its container>` or hot-reload via
     Telegram `/reload_config` / `POST /api/v1/reload_config`.

Keep it concise (the table in "Configuration" already lists the vars; this adds
the *how-to-fill-them* steps). No code changes.

## Optional cleanups (only if user opts in)

- **config.json tokens:** `freqtrade-crth-strategy/freqtrade-crth-strategy/config.json`
  currently has `jwt_secret_key` and `ws_token` set to the literal strings
  `"secrets.token_hex(32)"` / `"secrets.token_urlsafe(32)"` (command text, not
  generated values). Replace with freshly generated random values. The basic-auth
  `password` is already valid, so this is hygiene, not required for the
  webhook→freqtrade path.
- **docker-compose.yml:** remove the obsolete top-level `version: "3.9"` line in
  `fastapi-webhook-bot/fastapi-webhook-bot/docker-compose.yml` to silence the
  Compose v2 warning.

## Verification

- Re-read the README section for accuracy (commands, file references, the
  must-match relationships) and confirm no real secrets are written into it.
- If the token fix is applied, confirm `config.json` still parses as valid JSON
  and the two fields are non-placeholder random strings.
