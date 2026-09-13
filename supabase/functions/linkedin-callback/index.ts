/**
 * Permanent LinkedIn OAuth callback bridge.
 *
 * Register this function's URL once as the LinkedIn app's redirect URI and it
 * never changes. LinkedIn redirects the user's browser here with
 * `?code=...&state=...` (or `?error=...`); this function forwards the browser
 * to the local backend, which performs the token exchange and then redirects
 * on to the frontend. The browser is the transport, so the local backend
 * never needs a public tunnel.
 *
 * Override the target with the `LOCAL_CALLBACK_URL` function secret if the
 * backend is not on the default port.
 */

const LOCAL_CALLBACK =
  Deno.env.get("LOCAL_CALLBACK_URL") ?? "http://localhost:8000/oauth/callback/linkedin";

Deno.serve((req: Request): Response => {
  const incoming = new URL(req.url);

  if ([...incoming.searchParams.keys()].length === 0) {
    return new Response(
      "socialagent LinkedIn OAuth callback bridge.\n" +
        "Set this URL as the redirect URI in the LinkedIn app, then sign in from the app.\n",
      { status: 200, headers: { "content-type": "text/plain; charset=utf-8" } },
    );
  }

  const target = new URL(LOCAL_CALLBACK);
  incoming.searchParams.forEach((value, key) => target.searchParams.set(key, value));
  return Response.redirect(target.toString(), 302);
});
