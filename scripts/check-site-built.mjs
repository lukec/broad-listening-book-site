import { existsSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const siteIndex = path.join(repoRoot, "site", "index.html");

if (!existsSync(siteIndex) || !statSync(siteIndex).isFile()) {
  console.error(
    [
      "Expected a generated static site at ./site/index.html.",
      "Build it first with:",
      "",
      "  uv run broad-book-build",
    ].join("\n"),
  );
  process.exit(1);
}
