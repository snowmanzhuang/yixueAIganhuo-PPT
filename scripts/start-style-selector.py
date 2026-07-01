#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import functools
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional


HTML_FILE = "yixueAIganhuo_ppt_style_selector.html"
DEFAULT_PORT = 8765
DEFAULT_BACKGROUND_TTL_SECONDS = 3600


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def html_dir() -> Path:
    return skill_root() / "references" / "style_selector"


def port_available(port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def choose_port(preferred: int) -> int:
    if preferred == 0:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    if port_available(preferred):
        return preferred
    for port in range(preferred + 1, preferred + 100):
        if port_available(port):
            return port
    raise SystemExit(f"No available localhost port near {preferred}")


def validate_assets(root: Path) -> Path:
    html_path = root / HTML_FILE
    if not html_path.exists():
        raise SystemExit(f"HTML file not found: {html_path}")
    assets_dir = root / "assets"
    if not assets_dir.exists():
        raise SystemExit(f"Assets directory not found: {assets_dir}")
    return html_path


def wait_for_server(port: int, timeout_seconds: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(0.2)
            try:
                sock.connect(("127.0.0.1", port))
            except OSError:
                time.sleep(0.05)
                continue
            return True
    return False


def print_banner(url: str, file_url: str, *, background: bool, pid: Optional[int], ttl_seconds: int) -> None:
    print("", flush=True)
    print("yixueAIganhuo-PPT 风格选择器已启动", flush=True)
    print(f"点击打开：{url}", flush=True)
    print(f"本地文件兜底：{file_url}", flush=True)
    if background:
        pid_text = f"，PID {pid}" if pid else ""
        ttl_text = f"，约 {ttl_seconds} 秒后自动退出" if ttl_seconds > 0 else ""
        print(f"后台服务运行中{pid_text}{ttl_text}。", flush=True)
    else:
        print("提示：保持这个终端窗口运行；关闭窗口或 Ctrl+C 后链接会停止服务。", flush=True)
    print("", flush=True)


def serve(root: Path, port: int, ttl_seconds: int) -> int:
    handler = functools.partial(QuietHandler, directory=str(root))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        print(f"本地服务启动失败：{exc}", file=sys.stderr, flush=True)
        return 1

    if ttl_seconds > 0:
        timer = threading.Timer(ttl_seconds, server.shutdown)
        timer.daemon = True
        timer.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止风格选择器服务。", flush=True)
    finally:
        server.server_close()
    return 0


def spawn_background(port: int, ttl_seconds: int) -> subprocess.Popen:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--serve",
        "--port",
        str(port),
        "--ttl-seconds",
        str(ttl_seconds),
    ]
    kwargs: Dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start the yixueAIganhuo-PPT local style selector page."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Preferred localhost port. Use 0 for a random free port.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the style selector in the default browser after printing the URL.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start a detached local server, print the URL, then exit.",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=DEFAULT_BACKGROUND_TTL_SECONDS,
        help="Auto-stop seconds for background mode. Use 0 to disable.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    root = html_dir()
    html_path = validate_assets(root)
    port = choose_port(args.port)
    url = f"http://127.0.0.1:{port}/{HTML_FILE}"
    file_url = html_path.resolve().as_uri()

    if args.serve:
        return serve(root, port, args.ttl_seconds)

    if args.background:
        child = spawn_background(port, args.ttl_seconds)
        if not wait_for_server(port):
            print(f"后台服务启动失败，可尝试直接打开：{file_url}", file=sys.stderr, flush=True)
            return 1
        print_banner(url, file_url, background=True, pid=child.pid, ttl_seconds=args.ttl_seconds)
        if args.open:
            opened = webbrowser.open(url)
            if not opened:
                print("浏览器未自动打开，请手动点击上面的链接。", flush=True)
        return 0

    print_banner(url, file_url, background=False, pid=None, ttl_seconds=0)

    if args.open:
        opened = webbrowser.open(url)
        if not opened:
            print("浏览器未自动打开，请手动点击上面的链接。", flush=True)

    return serve(root, port, ttl_seconds=0)


if __name__ == "__main__":
    raise SystemExit(main())
