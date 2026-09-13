# Social Agent

Paste source links, and an agent turns them into a LinkedIn-ready post — with
an optional AI-generated image composed from the draft's headline — then
publishes only after you review and approve it. Dark, NotebookLM-styled UI;
TypeScript frontend, Python/FastAPI backend.

There is **no database**: the whole runtime state (sources, drafts, generated
images, LinkedIn connection) lives in one in-memory session and a "Clear
session" button wipes it.

```
/frontend             React + Tailwind UI (TypeScript)
/backend
  /ingestion          URL -> extracted page context (trafilatura + optional VLM)
  /templates          OpenRouter copy generation (LinkedIn now, Instagram-ready)
  /imaging            OpenRouter image generation + PIL caption composition
  /distribution       LinkedIn OAuth + publishing (provider-shaped for future platforms)
  /orchestrator       FastAPI HTTP API + the single in-memory session
  /media              generated images, served at /media (gitignored)
/shared               the wire contract (Source/Post/PostBundle types)
```

## Quickstart (two terminals)

**Backend** — from `backend/`, not the repo root (`routes.py` imports sibling
packages, so `backend/` must be on `sys.path`):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in OPENROUTER_API_KEY and the LinkedIn keys
python -m uvicorn orchestrator.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 — proxies /api and /media to :8000
```

Open `http://localhost:5173` and:

1. **(Optional) Add sources** in the left panel — they ground the draft in
   real facts. Each URL is fetched and its text extracted immediately; tick
   "Analyze page images too" to also run the slower OpenRouter vision pass.
   You can skip this entirely and just describe what you want in the composer.
2. **Pick a template** (Funding / Acquisition / Launch / Custom), optionally
   steer with the composer prompt, and hit **Generate posts**.
3. **Add an image** per draft if you want one — the agent writes the art
   direction, OpenRouter renders the background, and it is composed with the
   headline/subhead at 4:5, 1:1 or 16:9. Two optional guides:
   - **Style reference** (top right): upload an image and the model copies the
     same style as the image referenced — layout, palette and typography —
     while writing fresh copy. Generation then runs through the vision model
     to extract those design tokens.
   - **Web bg** (per card): search the web (Tavily) for a real photo about the
     post and pass it as a scene guide for the background.
4. **Approve** to publish. If LinkedIn isn't connected, the UI sends you
   through OAuth first; once connected, a confirmation dialog is the final
   permission step before the post goes live.
5. **Clear session** forgets sources, drafts, images and the LinkedIn
   connection.

## LinkedIn OAuth setup

LinkedIn requires an HTTPS redirect URL and rejects localhost, so this repo
ships a tiny Supabase Edge Function (`supabase/functions/linkedin-callback`)
that acts as a **permanent** callback bridge: LinkedIn redirects the browser
to the function, the function forwards it to the local backend, and the
backend does the token exchange. The URL never changes, so you register it
once and stop fighting rotating tunnels.

1. Create an app at <https://www.linkedin.com/developers/apps> and add the
   products **Share on LinkedIn** and **Sign in with LinkedIn using OpenID
   Connect**. Copy the client ID/secret into `backend/.env`.
2. Deploy the bridge once (from the repo root):

   ```bash
   supabase login
   supabase functions deploy linkedin-callback \
     --project-ref <your-project-ref> --no-verify-jwt --use-api
   ```

   Put its URL in `LINKEDIN_REDIRECT_URI` (`backend/.env`) and register the
   same URL in the LinkedIn app's Auth tab under **Redirect URLs**:

   ```
   https://<project-ref>.supabase.co/functions/v1/linkedin-callback
   ```

   The currently deployed bridge for this machine is already set in
   `backend/.env` — just register that URL in the LinkedIn portal.
3. `FRONTEND_SUCCESS_URL` (default `http://localhost:5173`) is where the
   browser lands after the callback; the query string carries
   `?connected=linkedin` or `?error=...`.

<details>
<summary>Fallback: cloudflared quick tunnel (URL changes on restart)</summary>

If you don't want to use Supabase, leave `LINKEDIN_REDIRECT_URI` empty, run
`cloudflared tunnel --url http://localhost:8000`, set `PUBLIC_BASE_URL` to
the printed URL, and register `PUBLIC_BASE_URL/oauth/callback/linkedin` in
the LinkedIn portal. You'll have to repeat that whenever the tunnel restarts.

</details>

## Configuration

All config lives in `backend/.env` (see `backend/.env.example`):

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Source analysis, copy generation and image generation |
| `TAVILY_API_KEY` | Optional; only the hidden web-image-search fallback uses it |
| `LINKEDIN_REDIRECT_URI` | Stable redirect registered with LinkedIn (Supabase bridge); preferred |
| `PUBLIC_BASE_URL` | Fallback base URL used only when `LINKEDIN_REDIRECT_URI` is empty |
| `FRONTEND_SUCCESS_URL` | Where the OAuth callback redirects the browser |
| `LINKEDIN_CLIENT_ID` / `_SECRET` | LinkedIn OAuth credentials |
| `MEDIA_DIR` | Where generated images are written (default `backend/media`) |

## Tests

```bash
cd backend
.venv/bin/python -m pytest        # provider + API tests, all HTTP mocked
cd ../frontend
npm run typecheck && npm run build
```

## The contract

`shared/types.ts` is the canonical shape of everything that crosses the
network. The frontend imports it directly; the Python backend hand-mirrors it
in `backend/orchestrator/schemas.py`. If you change one, change the other in
the same change — see `shared/README.md`.
