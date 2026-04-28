import {
  buildClearedSessionCookie,
  buildSessionCookie,
  createSignedSession,
  passwordMatches,
  readSignedSession,
} from "./auth.js";

const SHAPE_UP_TYPEKIT_CSS = "https://use.typekit.net/xig7qap.css";
const CLOUDFLARE_WEB_ANALYTICS_SRC = "https://static.cloudflareinsights.com/beacon.min.js";
const NOINDEX_POLICY = "noindex, nofollow, noarchive";
const LOGIN_PATH = "/login";
const LOGOUT_PATH = "/logout";

export default {
  async fetch(request, env) {
    const config = loadConfig(env);
    const url = new URL(request.url);
    let session = null;

    if (shouldRedirectToCanonicalHttps(url, config)) {
      return buildRedirectResponse(buildCanonicalHttpsUrl(url, config), 301);
    }

    if (url.pathname === "/robots.txt") {
      return buildRobotsResponse(config);
    }

    if (url.pathname === LOGIN_PATH) {
      return handleLoginRoute(request, env, config);
    }

    if (url.pathname === LOGOUT_PATH) {
      return handleLogoutRoute(request, config);
    }

    if (shouldProtectPath(url.pathname, config)) {
      session = await authenticateRequest(request, config);
      if (!session) {
        return redirectToLogin(url, config);
      }
    }

    return serveAsset(request, env, config, session);
  },
};

async function handleLoginRoute(request, env, config) {
  const url = new URL(request.url);
  const nextPath = safeNextPath(url.searchParams.get("next"), config.defaultAfterLoginPath);
  const isSecure = url.protocol === "https:";

  if (request.method === "POST") {
    if (!config.sharedPassword || !config.cookieSigningSecret) {
      return buildErrorResponse(
        "Worker secrets are not configured yet. Set SHARED_PASSWORD and COOKIE_SIGNING_SECRET before deploying.",
      );
    }

    const clientIp = request.headers.get("CF-Connecting-IP") || "unknown";
    const rateLimitResult = await env.LOGIN_POST_RATE_LIMITER.limit({
      key: `login:${clientIp}`,
    });
    if (!rateLimitResult.success) {
      return buildRateLimitedResponse();
    }

    const formData = await request.formData();
    const submittedPassword = String(formData.get("password") || "");
    const submittedNext = safeNextPath(formData.get("next"), config.defaultAfterLoginPath);
    const validPassword = await passwordMatches(submittedPassword, config.sharedPassword);

    if (!validPassword) {
      return renderLoginPage(config, {
        nextPath: submittedNext,
        errorMessage: "Login failed. Check the shared credentials and try again.",
      });
    }

    const signedSession = await createSignedSession(
      config.fixedUsername,
      config.cookieTtlSeconds,
      config.cookieSigningSecret,
    );

    const response = buildRedirectResponse(new URL(submittedNext, request.url), 302);
    response.headers.set(
      "Set-Cookie",
      buildSessionCookie(config.cookieName, signedSession, config.cookieTtlSeconds, isSecure),
    );
    response.headers.set("Cache-Control", "no-store");
    response.headers.set("X-Robots-Tag", NOINDEX_POLICY);
    return response;
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    return methodNotAllowed(["GET", "HEAD", "POST"]);
  }

  const existingSession = await authenticateRequest(request, config);
  if (existingSession) {
    return buildRedirectResponse(new URL(nextPath, request.url), 302);
  }

  return renderLoginPage(config, { nextPath });
}

async function handleLogoutRoute(request, config) {
  if (!["GET", "HEAD", "POST"].includes(request.method)) {
    return methodNotAllowed(["GET", "HEAD", "POST"]);
  }

  const url = new URL(request.url);
  const response = buildRedirectResponse(new URL(LOGIN_PATH, request.url), 302);
  response.headers.set("Set-Cookie", buildClearedSessionCookie(config.cookieName, url.protocol === "https:"));
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("X-Robots-Tag", NOINDEX_POLICY);
  return response;
}

async function authenticateRequest(request, config) {
  if (!config.cookieSigningSecret) {
    return null;
  }

  const session = await readSignedSession(
    request.headers.get("Cookie"),
    config.cookieName,
    config.cookieSigningSecret,
  );

  if (!session) {
    return null;
  }

  if (session.u !== config.fixedUsername) {
    return null;
  }

  return session;
}

async function serveAsset(request, env, config, session) {
  const assetResponse = await env.ASSETS.fetch(request);
  return withResponseHeaders(assetResponse, request, config, {
    injectLogoutControl: Boolean(session),
  });
}

function loadConfig(env) {
  const configuredCanonicalHost = normalizeHost(env.CANONICAL_HOST || "broadlisteningbook.com");
  const canonicalHost = configuredCanonicalHost.startsWith("www.")
    ? configuredCanonicalHost.slice(4)
    : configuredCanonicalHost;
  const wwwHost = normalizeHost(env.WWW_HOST || `www.${canonicalHost}`);

  return {
    authScope: normalizeEnum(env.AUTH_SCOPE, ["all", "ja-only", "ja-partial"], "all"),
    jaPublicPrefixes: String(env.JA_PUBLIC_PREFIXES || "00_,12_,13_")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    indexingMode: normalizeEnum(
      env.SEARCH_INDEXING_MODE,
      ["blocked", "allow-authenticated", "public-english"],
      "allow-authenticated",
    ),
    canonicalHost,
    wwwHost,
    fixedUsername: String(env.FIXED_USERNAME || "preview").trim() || "preview",
    cookieName: String(env.SESSION_COOKIE_NAME || "broad_listening_preview").trim() || "broad_listening_preview",
    cookieTtlSeconds: normalizePositiveInteger(env.COOKIE_TTL_SECONDS, 60 * 60 * 24 * 30),
    cookieSigningSecret: env.COOKIE_SIGNING_SECRET,
    sharedPassword: env.SHARED_PASSWORD,
    webAnalyticsToken: String(env.CLOUDFLARE_WEB_ANALYTICS_TOKEN || "").trim(),
    defaultAfterLoginPath: "/",
  };
}

function shouldProtectPath(pathname, config) {
  if (pathname === LOGIN_PATH || pathname === LOGOUT_PATH || pathname === "/robots.txt") {
    return false;
  }

  if (config.authScope === "all") {
    return true;
  }

  if (config.authScope === "ja-only") {
    return pathname === "/ja" || pathname.startsWith("/ja/");
  }

  // "ja-partial": protect Japanese pages except index, support pages, preface (00_), and tech articles (12_, 13_)
  if (!(pathname === "/ja" || pathname.startsWith("/ja/"))) {
    return false;
  }
  if (pathname === "/ja" || pathname === "/ja/" || pathname === "/ja/index.html") {
    return false;
  }
  const filename = pathname.split("/").pop() || "";
  if (filename === "about.html" || filename === "feedback.html") {
    return false;
  }
  return !config.jaPublicPrefixes.some((prefix) => filename.startsWith(prefix));
}

function shouldRedirectToCanonicalHttps(url, config) {
  const isConfiguredHost = url.hostname === config.canonicalHost || url.hostname === config.wwwHost;
  return isConfiguredHost && (url.protocol !== "https:" || url.hostname === config.wwwHost);
}

function buildCanonicalHttpsUrl(url, config) {
  const redirected = new URL(url.toString());
  if (redirected.hostname === config.wwwHost) {
    redirected.hostname = config.canonicalHost;
  }
  redirected.protocol = "https:";
  return redirected.toString();
}

function redirectToLogin(url, config) {
  const loginUrl = new URL(LOGIN_PATH, url.toString());
  loginUrl.searchParams.set("next", `${url.pathname}${url.search}`);
  const response = buildRedirectResponse(loginUrl, 302);
  response.headers.set("Cache-Control", "no-store");
  if (shouldApplyNoindex(url.pathname, config)) {
    response.headers.set("X-Robots-Tag", NOINDEX_POLICY);
  }
  return response;
}

function buildRedirectResponse(destination, status) {
  const location = destination instanceof URL ? destination.toString() : String(destination);
  return new Response(null, {
    status,
    headers: {
      Location: location,
    },
  });
}

function buildRobotsResponse(config) {
  const body = buildRobotsTxt(config);
  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=300",
    },
  });
}

function buildRobotsTxt(config) {
  if (config.indexingMode === "blocked") {
    return ["User-agent: *", "Disallow: /"].join("\n");
  }

  if (config.indexingMode === "allow-authenticated") {
    return [
      "User-agent: *",
      "Allow: /",
      "Disallow: /login",
      "Disallow: /logout",
    ].join("\n");
  }

  return [
    "User-agent: *",
    "Allow: /",
    "Disallow: /login",
    "Disallow: /logout",
  ].join("\n");
}

async function withResponseHeaders(response, request, config, options = {}) {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  const contentType = headers.get("Content-Type") || "";
  const shouldInjectLogout = options.injectLogoutControl && contentType.includes("text/html");
  const shouldInjectAnalytics = Boolean(config.webAnalyticsToken) && contentType.includes("text/html");

  if (shouldApplyNoindex(new URL(request.url).pathname, config)) {
    headers.set("X-Robots-Tag", NOINDEX_POLICY);
  }

  let body = response.body;
  if (shouldInjectLogout || shouldInjectAnalytics) {
    let html = await response.text();
    if (shouldInjectLogout) {
      html = injectLogoutControl(html);
    }
    if (shouldInjectAnalytics) {
      html = injectWebAnalytics(html, config.webAnalyticsToken);
    }
    body = html;
    headers.set("Content-Type", "text/html; charset=utf-8");
    headers.delete("Content-Length");
  }

  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function shouldApplyNoindex(pathname, config) {
  if (config.indexingMode === "blocked") {
    return true;
  }

  if (pathname === LOGIN_PATH || pathname === LOGOUT_PATH) {
    return true;
  }

  if (config.indexingMode === "allow-authenticated") {
    return false;
  }

  return shouldProtectPath(pathname, config);
}

function renderLoginPage(config, { nextPath, errorMessage = "" }) {
  const body = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="robots" content="noindex,nofollow" />
    <title>Broad Listening Book Preview</title>
    <link rel="preconnect" href="https://use.typekit.net" />
    <link rel="stylesheet" href="${SHAPE_UP_TYPEKIT_CSS}" />
    <style>
      :root {
        --ink: #231f20;
        --paper: #fffaf1;
        --accent: #e59fb3;
        --accent-strong: #c96d89;
        --line: #dacdb9;
        --panel: rgba(255, 255, 255, 0.88);
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        min-height: 100vh;
        font-family: ff-meta-serif-web-pro, Georgia, serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(229, 159, 179, 0.3), transparent 36%),
          linear-gradient(180deg, #fffdf8 0%, var(--paper) 100%);
      }

      main {
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 2rem;
      }

      .card {
        width: min(100%, 42rem);
        padding: 2.5rem;
        border: 1px solid var(--line);
        border-radius: 1.5rem;
        background: var(--panel);
        box-shadow: 0 1.5rem 4rem rgba(35, 31, 32, 0.08);
      }

      .eyebrow {
        display: inline-block;
        margin-bottom: 1rem;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        background: #fff2f6;
        color: #7d4155;
        font-family: ff-meta-web-pro, Arial, sans-serif;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      h1 {
        margin: 0;
        font-size: clamp(2.2rem, 5vw, 3.4rem);
        line-height: 1.05;
      }

      p {
        margin: 1rem 0 0;
        font-size: 1.05rem;
        line-height: 1.6;
      }

      form {
        display: grid;
        gap: 1rem;
        margin-top: 2rem;
      }

      label {
        display: grid;
        gap: 0.45rem;
        font-family: ff-meta-web-pro, Arial, sans-serif;
        font-size: 0.92rem;
        font-weight: 700;
      }

      input {
        width: 100%;
        padding: 0.95rem 1rem;
        border: 1px solid var(--line);
        border-radius: 0.85rem;
        background: white;
        color: var(--ink);
        font: inherit;
      }

      input[readonly] {
        background: #fbf6ee;
      }

      button {
        margin-top: 0.35rem;
        padding: 1rem 1.1rem;
        border: 0;
        border-radius: 999px;
        background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
        color: white;
        font-family: ff-meta-web-pro, Arial, sans-serif;
        font-size: 0.98rem;
        font-weight: 700;
        cursor: pointer;
      }

      .note {
        margin-top: 1.25rem;
        color: #6d6257;
        font-size: 0.95rem;
      }

      .error {
        margin-top: 1.25rem;
        padding: 0.9rem 1rem;
        border-radius: 0.9rem;
        background: #fff1f3;
        color: #8f2947;
        font-family: ff-meta-web-pro, Arial, sans-serif;
        font-size: 0.95rem;
        font-weight: 700;
      }
    </style>
  </head>
  <body>
    <main>
      <section class="card">
        <span class="eyebrow">Preview Access</span>
        <h1>Broad Listening<br />Book Site</h1>
        <p>
          This release is currently shared as a password-protected preview. Use the shared
          password to enter the site.
        </p>
        ${errorMessage ? `<div class="error">${escapeHtml(errorMessage)}</div>` : ""}
        <form method="post" action="${LOGIN_PATH}">
          <input type="hidden" name="next" value="${escapeHtml(nextPath)}" />
          <label>
            Password
            <input name="password" type="password" autocomplete="current-password" required />
          </label>
          <button type="submit">Enter Preview</button>
        </form>
        <p class="note">
          Successful login sets an HttpOnly session cookie for 30 days on this browser.
        </p>
      </section>
    </main>
  </body>
</html>`;

  const headers = new Headers({
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Robots-Tag": NOINDEX_POLICY,
  });

  const html = config.webAnalyticsToken ? injectWebAnalytics(body, config.webAnalyticsToken) : body;
  return new Response(html, { status: 200, headers });
}

function injectLogoutControl(html) {
  const snippet = `
<a href="${LOGOUT_PATH}" style="
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  padding: 0.7rem 1rem;
  border: 1px solid rgba(35, 31, 32, 0.14);
  border-radius: 999px;
  background: rgba(255, 250, 241, 0.92);
  color: #231f20;
  font-family: ff-meta-web-pro, Arial, sans-serif;
  font-size: 0.9rem;
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 0.6rem 1.8rem rgba(35, 31, 32, 0.08);
  backdrop-filter: blur(6px);
">Log out</a>`;

  if (html.includes("</body>")) {
    return html.replace("</body>", `${snippet}\n</body>`);
  }
  return `${html}\n${snippet}`;
}

function injectWebAnalytics(html, token) {
  if (html.includes(CLOUDFLARE_WEB_ANALYTICS_SRC)) {
    return html;
  }

  const beaconConfig = escapeHtml(JSON.stringify({ token }));
  const snippet = `<!-- Cloudflare Web Analytics --><script defer src="${CLOUDFLARE_WEB_ANALYTICS_SRC}" data-cf-beacon='${beaconConfig}'></script><!-- End Cloudflare Web Analytics -->`;

  if (html.includes("</head>")) {
    return html.replace("</head>", `    ${snippet}\n  </head>`);
  }
  return `${snippet}\n${html}`;
}

function buildErrorResponse(message) {
  return new Response(message, {
    status: 500,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function buildRateLimitedResponse() {
  return new Response("Too many login attempts. Try again later.", {
    status: 429,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function methodNotAllowed(methods) {
  return new Response("Method Not Allowed", {
    status: 405,
    headers: {
      Allow: methods.join(", "),
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}

function safeNextPath(candidate, fallback) {
  if (typeof candidate !== "string" || candidate.length === 0) {
    return fallback;
  }

  if (!candidate.startsWith("/") || candidate.startsWith("//")) {
    return fallback;
  }

  return candidate;
}

function normalizeHost(hostname) {
  return String(hostname || "")
    .trim()
    .toLowerCase();
}

function normalizeEnum(value, allowedValues, fallback) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  return allowedValues.includes(normalized) ? normalized : fallback;
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
