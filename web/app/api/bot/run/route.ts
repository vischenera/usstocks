import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const OWNER = "vischenera";
const REPO = "usstocks";
const WORKFLOW = "bot.yml";

// Dispatch the lightweight bot-replay workflow. Needs a GitHub token with
// Actions write access in the GITHUB_DISPATCH_TOKEN env var (Vercel project
// settings) — the replay itself runs in GitHub Actions, not here.
export async function POST() {
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    return NextResponse.json(
      {
        error:
          "GITHUB_DISPATCH_TOKEN is not set. Create a fine-grained GitHub token " +
          "(repo: usstocks, Actions: read & write), add it as an environment " +
          "variable in Vercel, and redeploy.",
      },
      { status: 501 },
    );
  }
  try {
    const res = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({ ref: "main" }),
        cache: "no-store",
      },
    );
    if (res.status === 204) {
      return NextResponse.json({
        ok: true,
        note: "Replay started — takes ~2 minutes. Refresh this page to see updated results.",
      });
    }
    const body = await res.text();
    return NextResponse.json(
      { error: `GitHub dispatch failed (${res.status}): ${body.slice(0, 300)}` },
      { status: 502 },
    );
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
