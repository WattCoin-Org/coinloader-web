// Vercel Routing Middleware: serve the Markdown twin of a page when the client asks for
// text/markdown. Middleware runs before the filesystem, so it can override "/" and existing
// .html files, which a `has`-header rewrite in vercel.json cannot (static files win over rewrites).
// Anything that is not a page URL, or a request that does not ask for Markdown, passes through untouched.

const PAGE = /^\/(?:(bots\/[a-z0-9-]+)|about|contact|privacy)?$/;

const MD_HEADERS = {
  "content-type": "text/markdown; charset=utf-8",
  "vary": "Accept",
  "cache-control": "public, max-age=0, must-revalidate",
};

const NOT_FOUND = `# Not found

This page does not exist.

- Product catalog (JSON): https://coinloader.com/catalog.json
- LLM catalog (text): https://coinloader.com/llms.txt
- Home (Markdown): https://coinloader.com/index.md
`;

function q(accept, type) {
  let best = -1;
  for (const part of accept.split(",")) {
    const [t, ...params] = part.trim().toLowerCase().split(";");
    if (t.trim() !== type) continue;
    const p = params.map((s) => s.trim()).find((s) => s.startsWith("q="));
    const v = p ? parseFloat(p.slice(2)) : 1;
    best = Math.max(best, Number.isNaN(v) ? 1 : v);
  }
  return best;
}

export function wantsMarkdown(accept) {
  if (!accept) return false;
  const md = q(accept, "text/markdown");
  return md > 0 && md >= q(accept, "text/html");
}

// Returns the twin path for a page URL, null for a non-page URL (pass through), or "" for an unknown page.
export function twinPath(pathname) {
  let p = pathname.replace(/\/index\.html$/, "/").replace(/\.html$/, "");
  if (p.length > 1) p = p.replace(/\/+$/, "");
  if (/\.[a-z0-9]+$/i.test(p) || p.startsWith("/runtime/") || p.startsWith("/_vercel/")) return null;
  if (!PAGE.test(p)) return "";
  return p === "/" ? "/index.md" : `${p}.md`;
}

function markdown404(method) {
  return new Response(method === "HEAD" ? null : NOT_FOUND, { status: 404, headers: MD_HEADERS });
}

export default async function middleware(request) {
  if (request.method !== "GET" && request.method !== "HEAD") return;
  if (!wantsMarkdown(request.headers.get("accept"))) return;
  const url = new URL(request.url);
  const twin = twinPath(url.pathname);
  if (twin === null) return;
  if (twin === "") return markdown404(request.method);
  const res = await fetch(new URL(twin, url), { method: request.method });
  if (!res.ok) return markdown404(request.method);
  return new Response(request.method === "HEAD" ? null : res.body, { status: 200, headers: MD_HEADERS });
}
