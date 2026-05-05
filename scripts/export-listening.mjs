import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const DATABASE_NAME = "broad-listening-book-listening";
const EXPORT_COLUMNS = [
  "id",
  "created_at",
  "lang",
  "page_path",
  "page_url",
  "page_title",
  "chapter_id",
  "chapter_title",
  "nearest_heading",
  "selection_text",
  "selection_text_sha256",
  "lens",
  "response_text",
  "response_text_sha256",
  "moderation_status",
  "moderation_reason",
  "user_agent_family",
  "client_country",
  "turnstile_verified",
  "export_consent",
  "schema_version",
];

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  printHelp();
  process.exit(0);
}

const query = buildQuery(args);
const wranglerArgs = ["d1", "execute", args.database, "--command", query, "--json"];
wranglerArgs.push(args.remote ? "--remote" : "--local");

const result = runWrangler(wranglerArgs);
const rows = extractRows(result.stdout);
const output = args.format === "csv" ? rowsToCsv(rows) : rowsToJsonl(rows);

if (args.output) {
  writeFileSync(args.output, output, "utf8");
} else {
  process.stdout.write(output);
}

function parseArgs(argv) {
  const parsed = {
    database: DATABASE_NAME,
    format: "jsonl",
    status: "accepted",
    lang: "",
    since: "",
    until: "",
    limit: 10000,
    output: "",
    remote: false,
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      parsed.help = true;
    } else if (arg === "--remote") {
      parsed.remote = true;
    } else if (arg === "--local") {
      parsed.remote = false;
    } else if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const value = argv[index + 1];
      if (value === undefined || value.startsWith("--")) {
        fail(`Missing value for ${arg}`);
      }
      index += 1;
      if (key === "database") parsed.database = value;
      else if (key === "format") parsed.format = value;
      else if (key === "status") parsed.status = value;
      else if (key === "lang") parsed.lang = value;
      else if (key === "since") parsed.since = value;
      else if (key === "until") parsed.until = value;
      else if (key === "limit") parsed.limit = Number.parseInt(value, 10);
      else if (key === "output") parsed.output = value;
      else fail(`Unknown option ${arg}`);
    } else {
      fail(`Unknown argument ${arg}`);
    }
  }

  if (!["jsonl", "csv"].includes(parsed.format)) {
    fail("--format must be jsonl or csv");
  }
  if (parsed.status && !["accepted", "all"].includes(parsed.status)) {
    fail("--status must be accepted or all");
  }
  if (parsed.lang && !["en", "ja"].includes(parsed.lang)) {
    fail("--lang must be en or ja");
  }
  if (!Number.isFinite(parsed.limit) || parsed.limit <= 0 || parsed.limit > 50000) {
    fail("--limit must be between 1 and 50000");
  }
  validateDateArg(parsed.since, "--since");
  validateDateArg(parsed.until, "--until");
  return parsed;
}

function buildQuery(options) {
  const where = [];
  if (options.status !== "all") {
    where.push(`moderation_status = ${sqlQuote(options.status)}`);
  }
  if (options.lang) {
    where.push(`lang = ${sqlQuote(options.lang)}`);
  }
  if (options.since) {
    where.push(`created_at >= ${sqlQuote(normalizeDateArg(options.since, "start"))}`);
  }
  if (options.until) {
    where.push(`created_at <= ${sqlQuote(normalizeDateArg(options.until, "end"))}`);
  }

  return [
    `SELECT ${EXPORT_COLUMNS.join(", ")}`,
    "FROM listening_responses",
    where.length ? `WHERE ${where.join(" AND ")}` : "",
    "ORDER BY created_at ASC",
    `LIMIT ${options.limit}`,
  ]
    .filter(Boolean)
    .join(" ");
}

function runWrangler(wranglerArgs) {
  let result = spawnSync("wrangler", wranglerArgs, { encoding: "utf8" });
  if (result.error && result.error.code === "ENOENT") {
    result = spawnSync("npx", ["wrangler", ...wranglerArgs], { encoding: "utf8" });
  }
  if (result.error) {
    fail(result.error.message);
  }
  if (result.status !== 0) {
    process.stderr.write(result.stderr || result.stdout);
    process.exit(result.status || 1);
  }
  return result;
}

function extractRows(stdout) {
  const text = stdout.trim();
  if (!text) return [];
  const jsonStart = findJsonStart(text);
  const parsed = JSON.parse(text.slice(jsonStart));
  const first = Array.isArray(parsed) ? parsed[0] : parsed;
  if (Array.isArray(first?.results)) return first.results;
  if (Array.isArray(first?.result?.[0]?.results)) return first.result[0].results;
  if (Array.isArray(parsed?.results)) return parsed.results;
  return [];
}

function findJsonStart(text) {
  const starts = [text.indexOf("["), text.indexOf("{")].filter((index) => index >= 0);
  return starts.length ? Math.min(...starts) : 0;
}

function rowsToJsonl(rows) {
  return rows.map((row) => JSON.stringify(row)).join("\n") + (rows.length ? "\n" : "");
}

function rowsToCsv(rows) {
  const header = EXPORT_COLUMNS.join(",");
  const body = rows
    .map((row) => EXPORT_COLUMNS.map((column) => csvCell(row[column])).join(","))
    .join("\n");
  return body ? `${header}\n${body}\n` : `${header}\n`;
}

function csvCell(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function sqlQuote(value) {
  return `'${String(value).replaceAll("'", "''")}'`;
}

function validateDateArg(value, label) {
  if (!value) return;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return;
  if (/^\d{4}-\d{2}-\d{2}T/.test(value) && !Number.isNaN(Date.parse(value))) return;
  fail(`${label} must be YYYY-MM-DD or an ISO timestamp`);
}

function normalizeDateArg(value, mode) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return mode === "end" ? `${value}T23:59:59.999Z` : `${value}T00:00:00.000Z`;
  }
  return new Date(value).toISOString();
}

function printHelp() {
  process.stdout.write(`Export reader-listening responses from Cloudflare D1.

Usage:
  npm run listening:export -- [options]

Options:
  --format jsonl|csv       Output format. Default: jsonl
  --status accepted|all    Moderation status filter. Default: accepted
  --lang en|ja             Optional language filter.
  --since YYYY-MM-DD       Optional inclusive lower date bound.
  --until YYYY-MM-DD       Optional inclusive upper date bound.
  --limit N                Maximum rows, 1-50000. Default: 10000
  --output PATH            Write to a file instead of stdout.
  --remote                 Query the deployed D1 database.
  --local                  Query the local D1 database. Default.
`);
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
