"""Fetch a user-supplied HTTP/HTTPS webpage through the local proxy server.

Usage:
    python client/fetch_test.py https://example.com
    python client/fetch_test.py www.python.org
    python client/fetch_test.py
"""
import base64
import json
import re
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

HOST = "127.0.0.1"
PORT = 9000
MAX_FRAME = 8 * 1024 * 1024


def recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Server closed connection before sending the full response")
        data.extend(chunk)
    return bytes(data)


def send_frame(sock, payload):
    raw = json.dumps(payload).encode("utf-8")
    if len(raw) > 64 * 1024:
        raise ValueError("Request is too large")
    sock.sendall(len(raw).to_bytes(4, "big") + raw)


def recv_frame(sock):
    size = int.from_bytes(recv_exact(sock, 4), "big")
    if size <= 0 or size > MAX_FRAME:
        raise ValueError(f"Invalid response frame size: {size}")
    return json.loads(recv_exact(sock, size).decode("utf-8"))


def normalize_url(value):
    """Accept a URL with or without an explicit http/https scheme."""
    value = value.strip()
    if not value:
        raise ValueError("Please enter a URL.")

    if "://" not in value:
        value = "https://" + value

    parsed = urlsplit(value)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS webpage URLs are supported.")
    if not parsed.hostname:
        raise ValueError("The URL must include a valid hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing embedded usernames or passwords are not supported.")
    if parsed.port not in (None, 80 if parsed.scheme.lower() == "http" else 443):
        raise ValueError("Only standard HTTP (80) and HTTPS (443) ports are supported.")

    # Remove fragments: they are browser-side anchors and are not sent to the web server.
    return urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc,
        parsed.path or "/",
        parsed.query,
        ""
    ))


def make_filename(url):
    """Create a readable, filesystem-safe filename from the requested URL."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "webpage").lower()
    path = parsed.path.strip("/")

    name = host if not path else f"{host}_{path.replace('/', '_')}"
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("._-")
    name = (name or "webpage")[:100]
    return f"{name}.html"


def unique_output_path(directory, filename):
    """Avoid overwriting an earlier download with the same generated name."""
    path = directory / filename
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def fetch(url):
    with socket.create_connection((HOST, PORT), timeout=8) as sock:
        sock.settimeout(25)
        send_frame(sock, {"type": "fetch", "url": url})
        return recv_frame(sock)


def main():
    raw_url = sys.argv[1] if len(sys.argv) > 1 else input("Enter website URL: ")

    try:
        url = normalize_url(raw_url)
        print(f"\nSending request through proxy: {url}")

        result = fetch(url)
        if not result.get("success"):
            print("\nFETCH FAILED:", result.get("error", "Unknown server error"))
            return 1

        content_type = result.get("content_type", "")
        if not (
            "text/html" in content_type.lower()
            or "application/xhtml+xml" in content_type.lower()
        ):
            print("\nFETCH FAILED: The server returned non-HTML content.")
            print("Content type:", content_type or "unknown")
            return 1

        body = base64.b64decode(result["body"], validate=True)
        output_dir = Path(__file__).resolve().parents[1] / "saved_pages"
        output_dir.mkdir(parents=True, exist_ok=True)

        final_url = result.get("final_url") or url
        output_file = unique_output_path(output_dir, make_filename(final_url))
        output_file.write_bytes(body)

        print("\nFETCH SUCCESSFUL")
        print("HTTP status:", result.get("status"))
        print("Content type:", content_type)
        print("Final URL:", final_url)
        print("Downloaded bytes:", len(body))
        print("Saved HTML:", output_file)
        return 0

    except ValueError as exc:
        print("\nINVALID URL:", exc)
        return 2
    except (OSError, ConnectionError, json.JSONDecodeError) as exc:
        print("\nCONNECTION / RESPONSE FAILED:", exc)
        print("Make sure the dashboard is open and the proxy server is ONLINE.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
