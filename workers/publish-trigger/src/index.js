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
  if (!res.ok) {
    console.error(eventType, "failed", res.status, await res.text());
  }
}

export default {
  async scheduled(_event, env, _ctx) {
    const token = env.GITHUB_PAT;
    if (!token) {
      console.error("GITHUB_PAT not set");
      return;
    }
    const repo = env.GITHUB_REPO || "gatlabes01/stat";
    for (const eventType of EVENTS) {
      await dispatch(eventType, token, repo);
    }
  },
};