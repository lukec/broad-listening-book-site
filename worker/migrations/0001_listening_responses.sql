CREATE TABLE IF NOT EXISTS listening_responses (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  lang TEXT NOT NULL,
  page_path TEXT NOT NULL,
  page_url TEXT NOT NULL,
  page_title TEXT NOT NULL,
  chapter_id TEXT,
  chapter_title TEXT,
  nearest_heading TEXT,
  selection_text TEXT NOT NULL,
  selection_text_sha256 TEXT NOT NULL,
  lens TEXT NOT NULL,
  response_text TEXT NOT NULL,
  response_text_sha256 TEXT NOT NULL,
  moderation_status TEXT NOT NULL,
  moderation_reason TEXT,
  user_agent_family TEXT,
  client_country TEXT,
  turnstile_verified INTEGER NOT NULL DEFAULT 0,
  export_consent TEXT NOT NULL DEFAULT 'private_analysis',
  schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_listening_created_at
  ON listening_responses(created_at);

CREATE INDEX IF NOT EXISTS idx_listening_lang
  ON listening_responses(lang);

CREATE INDEX IF NOT EXISTS idx_listening_page_path
  ON listening_responses(page_path);

CREATE INDEX IF NOT EXISTS idx_listening_lens
  ON listening_responses(lens);

CREATE INDEX IF NOT EXISTS idx_listening_moderation_status
  ON listening_responses(moderation_status);

CREATE INDEX IF NOT EXISTS idx_listening_response_hash
  ON listening_responses(response_text_sha256);

CREATE INDEX IF NOT EXISTS idx_listening_selection_response_hash
  ON listening_responses(selection_text_sha256, response_text_sha256, created_at);
