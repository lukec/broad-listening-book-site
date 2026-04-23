const encoder = new TextEncoder();
const decoder = new TextDecoder();

export async function createSignedSession(username, ttlSeconds, secret) {
  const nowSeconds = Math.floor(Date.now() / 1000);
  const payload = {
    u: username,
    iat: nowSeconds,
    exp: nowSeconds + ttlSeconds,
  };
  const serialized = JSON.stringify(payload);
  const encodedPayload = base64UrlEncode(encoder.encode(serialized));
  const signature = await signValue(encodedPayload, secret);
  return `${encodedPayload}.${signature}`;
}

export async function readSignedSession(cookieHeader, cookieName, secret) {
  const token = getCookie(cookieHeader, cookieName);
  if (!token) {
    return null;
  }

  const [encodedPayload, signature] = token.split(".");
  if (!encodedPayload || !signature) {
    return null;
  }

  const expectedSignature = await signValue(encodedPayload, secret);
  if (!(await timingSafeEqual(signature, expectedSignature))) {
    return null;
  }

  let payload;
  try {
    payload = JSON.parse(decoder.decode(base64UrlDecode(encodedPayload)));
  } catch {
    return null;
  }

  if (!payload || typeof payload !== "object") {
    return null;
  }

  if (typeof payload.exp !== "number" || payload.exp <= Math.floor(Date.now() / 1000)) {
    return null;
  }

  if (typeof payload.u !== "string" || payload.u.length === 0) {
    return null;
  }

  return payload;
}

export async function passwordMatches(providedPassword, expectedPassword) {
  if (!expectedPassword) {
    return false;
  }

  const [providedDigest, expectedDigest] = await Promise.all([
    sha256(providedPassword),
    sha256(expectedPassword),
  ]);

  return timingSafeEqualBytes(providedDigest, expectedDigest);
}

export function buildSessionCookie(name, value, maxAgeSeconds, isSecure) {
  const parts = [
    `${name}=${value}`,
    "HttpOnly",
    "Path=/",
    "SameSite=Lax",
    `Max-Age=${maxAgeSeconds}`,
  ];
  if (isSecure) {
    parts.push("Secure");
  }
  return parts.join("; ");
}

export function buildClearedSessionCookie(name, isSecure) {
  const parts = [
    `${name}=`,
    "HttpOnly",
    "Path=/",
    "SameSite=Lax",
    "Max-Age=0",
    "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
  ];
  if (isSecure) {
    parts.push("Secure");
  }
  return parts.join("; ");
}

async function signValue(value, secret) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return base64UrlEncode(new Uint8Array(signature));
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return new Uint8Array(digest);
}

async function timingSafeEqual(a, b) {
  return timingSafeEqualBytes(encoder.encode(a), encoder.encode(b));
}

function timingSafeEqualBytes(a, b) {
  if (a.length !== b.length) {
    return false;
  }

  let mismatch = 0;
  for (let index = 0; index < a.length; index += 1) {
    mismatch |= a[index] ^ b[index];
  }
  return mismatch === 0;
}

function getCookie(cookieHeader, name) {
  if (!cookieHeader) {
    return null;
  }

  for (const fragment of cookieHeader.split(";")) {
    const trimmed = fragment.trim();
    if (!trimmed) {
      continue;
    }
    const separator = trimmed.indexOf("=");
    const key = separator === -1 ? trimmed : trimmed.slice(0, separator);
    if (key !== name) {
      continue;
    }
    return separator === -1 ? "" : trimmed.slice(separator + 1);
  }

  return null;
}

function base64UrlEncode(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }

  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
  const binary = atob(`${normalized}${padding}`);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}
