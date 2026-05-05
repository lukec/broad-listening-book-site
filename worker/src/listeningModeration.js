const URL_PATTERN = /\b(?:https?:\/\/|www\.)\S+/gi;
const EMAIL_PATTERN = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i;
const PHONE_PATTERN = /(?:\+?\d[\s().-]*){9,}/;

const LEET_REPLACEMENTS = new Map([
  ["0", "o"],
  ["1", "i"],
  ["3", "e"],
  ["4", "a"],
  ["5", "s"],
  ["7", "t"],
  ["@", "a"],
  ["$", "s"],
]);

const BLOCK_PATTERNS = [
  {
    reason: "obscene_language",
    pattern:
      /\b(?:fuck(?:er|ing)?|shit(?:ty)?|bullshit|piss|cunt|dick|cock|pussy|asshole|bastard|bitch|motherfucker|porn|xxx)\b/i,
  },
  {
    reason: "abusive_slur",
    pattern:
      /\b(?:nigger|faggot|retard|kike|chink|spic|gook|tranny|whore|slut)\b/i,
  },
  {
    reason: "unsafe_threat",
    pattern:
      /\b(?:kill|murder|shoot|stab|bomb|rape|hang|lynch)\s+(?:you|them|him|her|us|everyone|people|all)\b/i,
  },
  {
    reason: "obscene_language",
    pattern: /(?:くたばれ|死ね|殺すぞ|ぶっ殺す|レイプ|強姦|ポルノ|ちんこ|まんこ|おまんこ|セックス|ファック|クソ野郎)/i,
  },
];

export function moderateListeningText(values) {
  const rawText = values.filter(Boolean).join(" ");
  const normalized = normalizeForModeration(rawText);

  if (EMAIL_PATTERN.test(rawText)) {
    return { ok: false, reason: "personal_information" };
  }

  if (PHONE_PATTERN.test(rawText)) {
    return { ok: false, reason: "personal_information" };
  }

  const urls = rawText.match(URL_PATTERN) || [];
  if (urls.length > 1) {
    return { ok: false, reason: "spam_links" };
  }

  if (/([a-z0-9!?.,])\1{18,}/i.test(normalized)) {
    return { ok: false, reason: "spam_repetition" };
  }

  if (normalized.length >= 60 && new Set(normalized.replace(/\s/g, "")).size <= 4) {
    return { ok: false, reason: "spam_repetition" };
  }

  for (const { reason, pattern } of BLOCK_PATTERNS) {
    if (pattern.test(normalized)) {
      return { ok: false, reason };
    }
  }

  return { ok: true, reason: "" };
}

function normalizeForModeration(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[013457@$]/g, (char) => LEET_REPLACEMENTS.get(char) || char)
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
