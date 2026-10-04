# InboxPilot AI 2.0

InboxPilot is a multi-provider AI email-intelligence product: a React/Vite frontend with a subtle 3D experience, a FastAPI backend, Google and Microsoft OAuth, encrypted token storage, LLM classification, semantic summaries, next-action extraction, filters and CSV export.

## Architecture

```text
frontend/  React + Vite + React Three Fiber + Framer Motion
backend/   FastAPI + provider adapters + encrypted SQLite storage
data/      Safe demonstration inbox
```

Both providers implement the same `EmailProvider` contract, so the dashboard is independent of Gmail or Outlook.

The dashboard is fully data-driven: category distribution, priority mix, confidence, next actions, AI model status and exports are calculated from the current mailbox response. The Settings page shows connection and AI configuration, supports sign-out without deleting saved credentials, and provides a separate destructive disconnect action.

### Connection lifecycle

- OAuth access and refresh tokens are encrypted in the backend database.
- Signing out clears only the seven-day browser session.
- Signing in again may require Google account identification, but does not force the consent screen again.
- Disconnect mailbox deletes the saved OAuth token record and user connection.
- Existing refresh tokens are preserved when Google omits a new refresh token on subsequent sign-ins.
- Expiring access tokens are refreshed server-side when a refresh token is available.

## LLM modes

Groq-hosted Llama is the default product-demo mode:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
```

For a private or self-hosted deployment, start Ollama and configure:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

For offline development without a model:

```env
LLM_PROVIDER=rules
```

The LLM receives bounded email excerpts as untrusted data and must return validated JSON containing category, priority, sentiment, summary, next action and confidence. Invalid responses and provider outages fall back to deterministic rules so the inbox remains usable.

## Run the interactive demo

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
uvicorn app.main:app --reload
```

Put the generated key in `TOKEN_ENCRYPTION_KEY` and replace `SESSION_SECRET` before starting the API.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and select **Open interactive demo**.

## Google configuration

1. Enable Gmail API in Google Cloud.
2. Configure the OAuth consent screen and add yourself as a test user.
3. Create a Web application OAuth client.
4. Add `http://localhost:8000/api/auth/google/callback` as an authorized redirect URI.
5. Add the client ID and secret to `backend/.env`.

## Microsoft configuration

1. Create an app registration in Microsoft Entra.
2. Add `http://localhost:8000/api/auth/microsoft/callback` as a Web redirect URI.
3. Create a client secret.
4. Add delegated permissions: `User.Read`, `Mail.Read`, `offline_access`, `openid`, `profile`, `email`.
5. Add the client ID and secret to `backend/.env`.

## Production checklist

- Serve both applications over HTTPS and use exact production callback URLs.
- Replace SQLite with PostgreSQL for multi-instance deployment.
- Move secrets and the Fernet key into a managed secret store.
- Add refresh-token rotation and provider token revocation.
- Add tenant-controlled redaction policies before external LLM processing.
- Add rate limits, background jobs, audit events, retention controls and legal pages.
- Complete provider verification before offering the app broadly.

## Validation

```bash
cd backend && pytest -q
cd frontend && npm run build
```
