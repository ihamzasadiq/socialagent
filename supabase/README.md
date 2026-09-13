# /supabase

The one deployed piece of this app: a tiny Edge Function that gives LinkedIn
a **permanent** HTTPS callback URL.

LinkedIn refuses `http://localhost` redirect URIs, and quick tunnels
(cloudflared, ngrok free without a static domain) change URL on every
restart, which would force you to update `LINKEDIN_REDIRECT_URI` and the
LinkedIn app config every time. Instead:

```
LinkedIn consent
      |  redirects the browser to
      v
https://<ref>.supabase.co/functions/v1/linkedin-callback?code&state   (never changes)
      |  302 forwards the browser to
      v
http://localhost:8000/oauth/callback/linkedin?code&state              (your backend)
```

The backend exchanges the code (using the Supabase URL as `redirect_uri`,
as required) and redirects the browser to `FRONTEND_SUCCESS_URL`. Since the
browser is the transport, the backend never needs a public tunnel at all.

## Deploy

From the repo root:

```bash
supabase login
supabase functions deploy linkedin-callback \
  --project-ref <your-project-ref> --no-verify-jwt --use-api
```

Then set the function URL in `backend/.env`:

```
LINKEDIN_REDIRECT_URI=https://<project-ref>.supabase.co/functions/v1/linkedin-callback
```

...and register the exact same URL in the LinkedIn app under **Auth ->
Redirect URLs**. You only do this once.

`--no-verify-jwt` makes the function publicly reachable (LinkedIn can't send
a Supabase JWT). That's safe here: the function only forwards OAuth
parameters, and the `state` value is validated single-use by the backend.

## Configuration

The function forwards to `http://localhost:8000/oauth/callback/linkedin` by
default. If the backend runs elsewhere, set a function secret:

```bash
supabase secrets set LOCAL_CALLBACK_URL=http://localhost:9000/oauth/callback/linkedin \
  --project-ref <your-project-ref>
```
