/**
 * Cloudflare Cron → GitHub repository_dispatch for trending + TMZ news workflows.
 * Secret: wrangler secret put GITHUB_PAT
 */
const EVENTS = ["publish-trending", "publish-news"];

async function dispatch(eventType, token, repo) {
  const res = await fetch(`https://api.github.com/repos/${repo}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "detailz-publish-trigger",
    },
    body: JSON.stringify({ event_type: eventType }),
  });
  const body = res.ok ? "" : await res.text();
  return { eventType, status: res.status, body: body.slice(0, 500) };
}

async function runDispatches(env) {
  const token = (env.GITHUB_PAT || "").trim();
  if (!token) {
    console.error("GITHUB_PAT not set");
    return [{ error: "GITHUB_PAT not set" }];
  }
  const repo = (env.GITHUB_REPO || "gatlabes01/stat").trim();
  const results = [];
  for (const eventType of EVENTS) {
    results.push(await dispatch(eventType, token, repo));
  }
  console.log(JSON.stringify(results));
  return results;
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(runDispatches(env));
  },
  /** Optional one-off test: GET /ping — does not call GitHub. */
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/ping") {
      return new Response(
        JSON.stringify({
          ok: true,
          has_pat: Boolean((env.GITHUB_PAT || "").trim()),
          repo: (env.GITHUB_REPO || "gatlabes01/stat").trim(),
        }),
        { headers: { "content-type": "application/json" } },
      );
    }
    return new Response("detailz-publish-trigger (cron only)", { status: 404 });
  },
};