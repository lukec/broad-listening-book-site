#!/usr/bin/env node

const DEFAULT_BASE_URL = "https://broadlisteningbook.com";
const DEFAULT_START_PATHS = ["/", "/en/", "/ja/"];
const DEFAULT_TIMEOUT_MS = 15000;
const DEFAULT_MAX_PAGES = 1000;
const ASSET_EXTENSIONS = new Set([
  ".avif",
  ".css",
  ".gif",
  ".ico",
  ".jpeg",
  ".jpg",
  ".js",
  ".json",
  ".map",
  ".pdf",
  ".png",
  ".svg",
  ".txt",
  ".webp",
  ".woff",
  ".woff2",
  ".xml",
]);

function parseArgs(argv) {
  const options = {
    baseUrl: DEFAULT_BASE_URL,
    startPaths: [],
    timeoutMs: DEFAULT_TIMEOUT_MS,
    maxPages: DEFAULT_MAX_PAGES,
    verbose: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--base-url") {
      options.baseUrl = requireValue(argv, (index += 1), arg);
    } else if (arg === "--start") {
      options.startPaths.push(requireValue(argv, (index += 1), arg));
    } else if (arg === "--timeout-ms") {
      options.timeoutMs = parsePositiveInteger(requireValue(argv, (index += 1), arg), arg);
    } else if (arg === "--max-pages") {
      options.maxPages = parsePositiveInteger(requireValue(argv, (index += 1), arg), arg);
    } else if (arg === "--verbose") {
      options.verbose = true;
    } else if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    } else if (/^https?:\/\//.test(arg)) {
      options.baseUrl = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (options.startPaths.length === 0) {
    options.startPaths = DEFAULT_START_PATHS;
  }
  options.baseUrl = normalizeBaseUrl(options.baseUrl);
  return options;
}

function requireValue(argv, index, flag) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`Expected a value after ${flag}`);
  }
  return value;
}

function parsePositiveInteger(value, flag) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`Expected ${flag} to be a positive integer`);
  }
  return parsed;
}

function normalizeBaseUrl(value) {
  const url = new URL(value);
  url.hash = "";
  url.search = "";
  if (!url.pathname.endsWith("/")) {
    url.pathname = `${url.pathname}/`;
  }
  return url;
}

function printUsage() {
  console.log(`Usage:
  npm run check:live-images
  npm run check:live-images -- --base-url https://broadlisteningbook.com
  npm run check:live-images -- --start /en/ --start /ja/00_%E6%9C%AC%E6%9B%B8%E3%81%AE%E8%AA%AD%E3%81%BF%E3%81%8B%E3%81%9F.html

Options:
  --base-url <url>     Site origin to crawl. Defaults to ${DEFAULT_BASE_URL}
  --start <path-or-url>  Start path or URL. Can be repeated.
  --timeout-ms <ms>    Per-request timeout. Defaults to ${DEFAULT_TIMEOUT_MS}
  --max-pages <count>  Crawl limit for HTML pages. Defaults to ${DEFAULT_MAX_PAGES}
  --verbose            Print skipped redirects and protected pages.
`);
}

function sameOriginUrl(value, pageUrl, baseUrl) {
  let resolved;
  try {
    resolved = new URL(decodeHtmlAttribute(value), pageUrl);
  } catch (_) {
    return null;
  }

  if (!["http:", "https:"].includes(resolved.protocol)) {
    return null;
  }
  if (resolved.origin !== baseUrl.origin) {
    return null;
  }
  resolved.hash = "";
  return resolved;
}

function imageUrl(value, pageUrl) {
  const decoded = decodeHtmlAttribute(value).trim();
  if (!decoded || decoded.startsWith("data:")) {
    return null;
  }
  try {
    const resolved = new URL(decoded, pageUrl);
    if (!["http:", "https:"].includes(resolved.protocol)) {
      return null;
    }
    resolved.hash = "";
    return resolved;
  } catch (_) {
    return null;
  }
}

function decodeHtmlAttribute(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", '"')
    .replaceAll("&#x27;", "'")
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">");
}

function shouldCrawlPage(url, baseUrl) {
  if (url.origin !== baseUrl.origin) {
    return false;
  }
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/assets/") || url.pathname.startsWith("/images/")) {
    return false;
  }
  const extension = extensionForPath(url.pathname);
  return !extension || extension === ".html";
}

function extensionForPath(pathname) {
  const lastSegment = pathname.split("/").pop() || "";
  const dotIndex = lastSegment.lastIndexOf(".");
  if (dotIndex === -1) {
    return "";
  }
  return lastSegment.slice(dotIndex).toLowerCase();
}

function extractLinks(html, pageUrl, baseUrl) {
  const links = [];
  for (const match of html.matchAll(/<a\b[^>]*\bhref=(["'])(.*?)\1/gis)) {
    const url = sameOriginUrl(match[2], pageUrl, baseUrl);
    if (url && shouldCrawlPage(url, baseUrl)) {
      links.push(url.href);
    }
  }
  return links;
}

function extractImages(html, pageUrl) {
  const images = [];

  for (const match of html.matchAll(/<img\b[^>]*\bsrc=(["'])(.*?)\1/gis)) {
    const url = imageUrl(match[2], pageUrl);
    if (url) {
      images.push({ pageUrl: pageUrl.href, imageUrl: url.href, source: "img[src]" });
    }
  }

  for (const match of html.matchAll(/\bsrcset=(["'])(.*?)\1/gis)) {
    for (const candidate of parseSrcset(match[2])) {
      const url = imageUrl(candidate, pageUrl);
      if (url) {
        images.push({ pageUrl: pageUrl.href, imageUrl: url.href, source: "srcset" });
      }
    }
  }

  return images;
}

function parseSrcset(srcset) {
  return decodeHtmlAttribute(srcset)
    .split(",")
    .map((part) => part.trim().split(/\s+/)[0])
    .filter(Boolean);
}

async function fetchWithTimeout(url, options) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs);
  try {
    return await fetch(url, {
      headers: options.headers || {},
      redirect: options.redirect || "manual",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function crawl(options) {
  const queue = options.startPaths.map((startPath) => new URL(startPath, options.baseUrl).href);
  const seenPages = new Set();
  const seenImages = new Map();
  const pageFailures = [];
  const skippedPages = [];
  const redirectedPages = [];

  while (queue.length > 0 && seenPages.size < options.maxPages) {
    const pageHref = queue.shift();
    if (!pageHref || seenPages.has(pageHref)) {
      continue;
    }
    seenPages.add(pageHref);

    let response;
    try {
      response = await fetchWithTimeout(pageHref, options);
    } catch (error) {
      pageFailures.push({ pageUrl: pageHref, reason: error.message || String(error) });
      continue;
    }

    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("location") || "";
      const redirectUrl = location ? sameOriginUrl(location, new URL(pageHref), options.baseUrl) : null;
      if (
        redirectUrl
        && redirectUrl.pathname !== "/login"
        && shouldCrawlPage(redirectUrl, options.baseUrl)
        && !seenPages.has(redirectUrl.href)
      ) {
        redirectedPages.push({ pageUrl: pageHref, status: response.status, location: redirectUrl.href });
        queue.unshift(redirectUrl.href);
        continue;
      }
      skippedPages.push({
        pageUrl: pageHref,
        status: response.status,
        location,
      });
      continue;
    }

    if (response.status === 401 || response.status === 403) {
      skippedPages.push({ pageUrl: pageHref, status: response.status, location: "" });
      continue;
    }

    if (!response.ok) {
      pageFailures.push({ pageUrl: pageHref, reason: `HTTP ${response.status}` });
      continue;
    }

    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("text/html")) {
      continue;
    }

    const html = await response.text();
    const pageUrl = new URL(pageHref);

    for (const image of extractImages(html, pageUrl)) {
      if (!seenImages.has(image.imageUrl)) {
        seenImages.set(image.imageUrl, []);
      }
      seenImages.get(image.imageUrl).push({ pageUrl: image.pageUrl, source: image.source });
    }

    for (const link of extractLinks(html, pageUrl, options.baseUrl)) {
      if (!seenPages.has(link)) {
        queue.push(link);
      }
    }
  }

  return { seenPages, seenImages, pageFailures, skippedPages, redirectedPages };
}

async function checkImages(seenImages, options) {
  const imageFailures = [];

  for (const [url, references] of seenImages.entries()) {
    let response;
    try {
      response = await fetchWithTimeout(url, {
        ...options,
        headers: {
          Accept: "image/*,*/*;q=0.8",
          Range: "bytes=0-0",
        },
        redirect: "follow",
      });
      if (response.body) {
        await response.body.cancel();
      }
    } catch (error) {
      imageFailures.push({ imageUrl: url, references, reason: error.message || String(error) });
      continue;
    }

    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
      imageFailures.push({ imageUrl: url, references, reason: `HTTP ${response.status}` });
    } else if (!contentType.toLowerCase().startsWith("image/")) {
      imageFailures.push({ imageUrl: url, references, reason: `Unexpected content-type: ${contentType || "none"}` });
    }
  }

  return imageFailures;
}

function printFailures(title, failures, formatter) {
  if (failures.length === 0) {
    return;
  }
  console.error(`\n${title}`);
  for (const failure of failures.slice(0, 50)) {
    console.error(formatter(failure));
  }
  if (failures.length > 50) {
    console.error(`... and ${failures.length - 50} more`);
  }
}

try {
  const options = parseArgs(process.argv.slice(2));
  const crawlResult = await crawl(options);
  const imageFailures = await checkImages(crawlResult.seenImages, options);

  if (options.verbose && crawlResult.redirectedPages.length > 0) {
    console.log("Followed same-origin redirects:");
    for (const page of crawlResult.redirectedPages) {
      console.log(`- ${page.status} ${page.pageUrl} -> ${page.location}`);
    }
  }

  if (options.verbose && crawlResult.skippedPages.length > 0) {
    console.log("Skipped protected or external redirects:");
    for (const page of crawlResult.skippedPages) {
      console.log(`- ${page.status} ${page.pageUrl}${page.location ? ` -> ${page.location}` : ""}`);
    }
  }

  if (options.verbose) {
    printFailures("Page crawl warnings:", crawlResult.pageFailures, (failure) => {
      return `- ${failure.pageUrl}: ${failure.reason}`;
    });
  }

  printFailures("Image failures:", imageFailures, (failure) => {
    const firstReference = failure.references[0];
    return `- ${failure.imageUrl}: ${failure.reason}\n  referenced by ${firstReference.pageUrl} (${firstReference.source})`;
  });

  const pageCount = crawlResult.seenPages.size;
  const imageCount = crawlResult.seenImages.size;
  const skippedCount = crawlResult.skippedPages.length;
  const redirectCount = crawlResult.redirectedPages.length;
  console.log(`Checked ${imageCount} image URL(s) across ${pageCount} page(s); followed ${redirectCount} redirect(s); skipped ${skippedCount} protected/external redirect(s).`);

  if (imageFailures.length > 0) {
    process.exit(1);
  }
} catch (error) {
  console.error(error.message || String(error));
  console.error("");
  printUsage();
  process.exit(1);
}
