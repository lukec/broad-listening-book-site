from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import posixpath
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlsplit

from watchdog.events import DirModifiedEvent, FileClosedEvent, FileCreatedEvent, FileModifiedEvent, FileMovedEvent, FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

LOGGER = logging.getLogger("broad_book_site")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DEBOUNCE_MS = 700
SITE_REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_RELOAD_SNIPPET = """<script>
(() => {
  const protocol = window.location.protocol === 'https:' ? 'https' : 'http';
  const source = new EventSource(`${protocol}://${window.location.host}/__events`);
  source.addEventListener('reload', (event) => {
    try {
      const payload = JSON.parse(event.data || '{}');
      console.debug('[broad-book-site] reload', payload);
    } catch (_) {}
    window.location.reload();
  });
  source.onerror = () => console.debug('[broad-book-site] live reload disconnected; retrying');
})();
</script>"""
WATCH_EXTENSIONS = {
    ".md", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".txt", ".json", ".py"
}
WATCH_BASENAMES = {"book_order.txt", "pyproject.toml", "uv.lock"}
WATCH_DIR_PREFIXES = (
    "en/",
    "images/",
    "column/",
    "scripts/",
    "memo/",
    "interview_questions/",
    "code/",
    "wip-nishio/",
)


@dataclass
class BuildState:
    repo_root: Path
    html_root: Path
    debounce_ms: int = DEFAULT_DEBOUNCE_MS
    generation: int = 0
    last_build_ok: bool = False
    last_build_started: float | None = None
    last_build_finished: float | None = None
    last_error: str = ""
    last_trigger: str = "startup"
    building: bool = False
    clients: set[queue.Queue[str | None]] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)
    trigger_event: threading.Event = field(default_factory=threading.Event)
    stop_event: threading.Event = field(default_factory=threading.Event)

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "generation": self.generation,
                "last_build_ok": self.last_build_ok,
                "last_build_started": self.last_build_started,
                "last_build_finished": self.last_build_finished,
                "last_error": self.last_error,
                "last_trigger": self.last_trigger,
                "building": self.building,
            }

    def add_client(self) -> queue.Queue[str | None]:
        q: queue.Queue[str | None] = queue.Queue()
        with self.lock:
            self.clients.add(q)
        return q

    def remove_client(self, q: queue.Queue[str | None]) -> None:
        with self.lock:
            self.clients.discard(q)

    def broadcast_reload(self, reason: str) -> None:
        payload = json.dumps({
            "reason": reason,
            "generation": self.generation,
            "built_at": self.last_build_finished,
        })
        with self.lock:
            clients = list(self.clients)
        for client in clients:
            client.put(payload)


class BuildTriggerHandler(FileSystemEventHandler):
    def __init__(self, state: BuildState) -> None:
        self.state = state

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory or isinstance(event, DirModifiedEvent):
            return
        if not isinstance(event, (FileModifiedEvent, FileCreatedEvent, FileMovedEvent, FileClosedEvent)):
            return
        src_path = getattr(event, "src_path", None)
        if not src_path:
            return
        path = Path(src_path)
        try:
            rel = path.relative_to(self.state.repo_root).as_posix()
        except ValueError:
            return
        if is_ignored(rel):
            return
        if should_watch(rel):
            LOGGER.info("change detected: %s", rel)
            self.state.last_trigger = rel
            self.state.trigger_event.set()


def is_ignored(rel_path: str) -> bool:
    rel_path = rel_path.lstrip("./")
    parts = Path(rel_path).parts
    return any(part in {"html", ".git", ".venv", "__pycache__"} for part in parts)


def should_watch(rel_path: str) -> bool:
    rel_path = rel_path.lstrip("./")
    basename = posixpath.basename(rel_path)
    if basename in WATCH_BASENAMES:
        return True
    if any(rel_path.startswith(prefix) for prefix in WATCH_DIR_PREFIXES):
        return True
    return Path(rel_path).suffix.lower() in WATCH_EXTENSIONS


def resolve_build_command(state: BuildState) -> list[str]:
    uv_bin = os.environ.get("UV_BIN") or shutil.which("uv")
    if uv_bin:
        return [
            uv_bin,
            "run",
            "python",
            "-m",
            "broad_listening_book_site.web_build",
            "--repo-root",
            str(state.repo_root),
            "--output-dir",
            str(state.html_root),
        ]
    return [
        sys.executable,
        "-m",
        "broad_listening_book_site.web_build",
        "--repo-root",
        str(state.repo_root),
        "--output-dir",
        str(state.html_root),
    ]


def run_build(state: BuildState) -> bool:
    command = resolve_build_command(state)
    with state.lock:
        state.building = True
        state.last_build_started = time.time()
        state.last_error = ""
    LOGGER.info("building HTML via site repo: %s", " ".join(command))
    result = subprocess.run(
        command,
        cwd=SITE_REPO_ROOT,
        text=True,
        capture_output=True,
    )
    with state.lock:
        state.last_build_finished = time.time()
        state.building = False
        state.last_build_ok = result.returncode == 0
        if result.returncode == 0:
            state.generation += 1
        else:
            state.last_error = (result.stderr or result.stdout).strip()[-4000:]
    if result.returncode == 0:
        LOGGER.info("build complete (generation %s)", state.generation)
        if result.stdout.strip():
            LOGGER.info(result.stdout.strip())
        return True
    LOGGER.error("build failed: %s", state.last_error)
    return False


def build_loop(state: BuildState) -> None:
    pending_reason = "startup"
    while not state.stop_event.is_set():
        state.trigger_event.wait(timeout=0.5)
        if not state.trigger_event.is_set():
            continue
        state.trigger_event.clear()
        time.sleep(state.debounce_ms / 1000)
        while state.trigger_event.is_set():
            state.trigger_event.clear()
            time.sleep(state.debounce_ms / 1000)
        pending_reason = state.last_trigger
        ok = run_build(state)
        if ok:
            state.broadcast_reload(pending_reason)


class BookRequestHandler(BaseHTTPRequestHandler):
    server_version = "BroadListeningBookSite/0.1"

    def do_GET(self) -> None:
        split = urlsplit(self.path)
        path = unquote(split.path)
        if path == "/__health":
            self._handle_health()
            return
        if path == "/__events":
            self._handle_events()
            return
        self._serve_file(path)

    def log_message(self, fmt: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.client_address[0], fmt % args)

    @property
    def state(self) -> BuildState:
        return self.server.state  # type: ignore[attr-defined]

    def _handle_health(self) -> None:
        payload = json.dumps(self.state.snapshot(), indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_events(self) -> None:
        client = self.state.add_client()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            initial = json.dumps(self.state.snapshot())
            self.wfile.write(f"event: ready\ndata: {initial}\n\n".encode("utf-8"))
            self.wfile.flush()
            while True:
                try:
                    payload = client.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                if payload is None:
                    break
                self.wfile.write(f"event: reload\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.state.remove_client(client)

    def _serve_file(self, raw_path: str) -> None:
        safe_path = posixpath.normpath(raw_path)
        if safe_path in {".", "/"}:
            safe_path = "/index.html"
        rel = safe_path.lstrip("/")
        html_root = self.state.html_root.resolve()
        repo_root = self.state.repo_root.resolve()
        primary_path = (html_root / rel).resolve()

        file_path: Path | None = None
        try:
            primary_path.relative_to(html_root)
            file_path = primary_path
        except ValueError:
            repo_candidate = (repo_root / rel).resolve()
            try:
                repo_candidate.relative_to(repo_root)
                file_path = repo_candidate
            except ValueError:
                self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
                return

        if file_path.is_dir():
            index_candidate = file_path / "index.html"
            if index_candidate.exists():
                file_path = index_candidate

        if not file_path.exists():
            fallback = html_root / "index.html"
            if fallback.exists() and not rel.startswith(("images/", "column/", "en/", "ja/", "assets/")):
                file_path = fallback
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        data = file_path.read_bytes()
        if content_type.startswith("text/html"):
            text = data.decode("utf-8")
            data = inject_live_reload(text).encode("utf-8")
            content_type = "text/html; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # This server is for live editing, so every asset should bypass caches.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


class BookHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], state: BuildState):
        super().__init__(server_address, handler)
        self.state = state


def inject_live_reload(html_text: str) -> str:
    if "/__events" in html_text:
        return html_text
    if "</body>" in html_text:
        return html_text.replace("</body>", LIVE_RELOAD_SNIPPET + "\n</body>")
    return html_text + LIVE_RELOAD_SNIPPET


def start_observer(state: BuildState) -> Observer:
    observer = Observer()
    observer.schedule(BuildTriggerHandler(state), str(state.repo_root), recursive=True)
    observer.start()
    return observer


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live-reload dev server for the Broad Listening web site")
    parser.add_argument("--book-repo", type=Path, default=Path("../broad-listening-book"), help="Path to manuscript repo")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port (default: 8765)")
    parser.add_argument("--debounce-ms", type=int, default=DEFAULT_DEBOUNCE_MS, help="Debounce before rebuilding")
    parser.add_argument("--skip-initial-build", action="store_true", help="Skip the initial HTML build")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    repo_root = args.book_repo.expanduser().resolve()
    html_root = SITE_REPO_ROOT / "site"
    if not repo_root.exists():
        raise SystemExit(f"Book repo not found: {repo_root}")

    state = BuildState(repo_root=repo_root, html_root=html_root, debounce_ms=args.debounce_ms)
    if not args.skip_initial_build:
        if not run_build(state):
            LOGGER.warning("initial build failed; server will still start and keep watching")

    observer = start_observer(state)
    thread = threading.Thread(target=build_loop, args=(state,), daemon=True, name="build-loop")
    thread.start()

    server = BookHTTPServer((args.host, args.port), BookRequestHandler, state)
    LOGGER.info("serving %s at http://%s:%s", html_root, args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("shutting down")
    finally:
        state.stop_event.set()
        with state.lock:
            clients = list(state.clients)
        for client in clients:
            client.put(None)
        observer.stop()
        observer.join(timeout=5)
        server.server_close()
