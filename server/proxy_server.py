"""
Advanced Proxy System - TCP proxy server.

Stage 2: TCP listener, bounded worker pool, synchronized sessions.
Stage 3: Validated HTTP/HTTPS webpage fetching and framed responses.

Security:
- Binds to loopback by default.
- Only HTTP/HTTPS URLs on ports 80/443 are accepted.
- Rejects private, loopback, link-local, reserved and non-global IP destinations.
- Revalidates redirect targets.
- Limits downloaded response bodies.
"""

import base64
import ipaddress
import json
import socket
import threading
import time
import ssl
import certifi
import uuid
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from database.request_store import record_request


MAX_FRAME_SIZE = 8 * 1024 * 1024
MAX_REQUEST_SIZE = 64 * 1024
MAX_BODY_SIZE = 5 * 1024 * 1024
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_WORKERS = 20
FETCH_TIMEOUT = 12


def _recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Client disconnected before sending a complete message")
        data.extend(chunk)
    return bytes(data)


def recv_json_frame(sock, limit=MAX_REQUEST_SIZE):
    header = _recv_exact(sock, 4)
    size = int.from_bytes(header, "big")
    if size <= 0 or size > limit:
        raise ValueError(f"Invalid message size: {size}")
    raw = _recv_exact(sock, size)
    return json.loads(raw.decode("utf-8"))


def send_json_frame(sock, payload):
    raw = json.dumps(payload).encode("utf-8")
    if len(raw) > MAX_FRAME_SIZE:
        raise ValueError("Response is too large")
    sock.sendall(len(raw).to_bytes(4, "big") + raw)


def validate_public_http_url(url):
    """Validate scheme, credentials, port and resolved destination IPs."""
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("URL is missing or too long")

    parsed = urllib.parse.urlsplit(url)

    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are supported")

    if not parsed.hostname:
        raise ValueError("URL must contain a hostname")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing embedded credentials are not allowed")

    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid URL port")

    expected_port = 443 if parsed.scheme.lower() == "https" else 80
    if port is not None and port != expected_port:
        raise ValueError("Only standard HTTP (80) and HTTPS (443) ports are allowed")

    hostname = parsed.hostname.rstrip(".")
    if hostname.lower() == "localhost":
        raise ValueError("Localhost destinations are blocked")

    try:
        literal_ip = ipaddress.ip_address(hostname)
        addresses = [literal_ip]
    except ValueError:
        try:
            records = socket.getaddrinfo(
                hostname,
                port or expected_port,
                type=socket.SOCK_STREAM
            )
        except socket.gaierror as exc:
            raise ValueError(f"Could not resolve hostname: {exc}")

        addresses = []
        for record in records:
            sockaddr = record[4]
            addresses.append(ipaddress.ip_address(sockaddr[0]))

    if not addresses:
        raise ValueError("Hostname did not resolve to an IP address")

    for address in addresses:
        if not address.is_global:
            raise ValueError("Private, local or reserved network destinations are blocked")

    return parsed


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects that point to non-public or unsupported destinations."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ProxyServerController:
    """Owns the listening socket, accept loop and worker thread pool."""

    def __init__(
        self,
        on_log=None,
        on_status=None,
        on_metrics=None,
        on_session_add=None,
        on_session_remove=None,
        on_request=None,
        max_workers=DEFAULT_WORKERS,
    ):
        self.on_log = on_log or (lambda message: None)
        self.on_status = on_status or (lambda running, host, port: None)
        self.on_metrics = on_metrics or (lambda **values: None)
        self.on_session_add = on_session_add or (lambda *args, **kwargs: None)
        self.on_session_remove = on_session_remove or (lambda session_id: None)
        self.on_request = on_request or (lambda url, status, elapsed: None)

        self.max_workers = max_workers
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT

        self._server_socket = None
        self._accept_thread = None
        self._executor = None
        self._stop_event = threading.Event()

        self._state_lock = threading.Lock()
        self._clients_lock = threading.Lock()
        self._metrics_lock = threading.Lock()

        self._client_sockets = {}
        self._active_clients = 0
        self._active_workers = 0
        self._total_requests = 0
        self._successful_requests = 0
        self._total_latency_ms = 0.0
        self._bytes_in = 0
        self._bytes_out = 0

    @property
    def is_running(self):
        with self._state_lock:
            return self._server_socket is not None and not self._stop_event.is_set()

    def start(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError("Port must be between 1 and 65535")

        with self._state_lock:
            if self._server_socket is not None:
                self.on_log("Start ignored: server is already running.")
                return

            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind((host, port))
                listener.listen(100)
                listener.settimeout(1.0)
            except Exception:
                listener.close()
                raise

            self.host = host
            self.port = port
            self._server_socket = listener
            self._stop_event.clear()
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="ProxyWorker",
            )
            self._accept_thread = threading.Thread(
                target=self._accept_loop,
                name="ProxyAcceptLoop",
                daemon=True,
            )
            self._accept_thread.start()

        self.on_status(True, self.host, self.port)
        self.on_log(
            f"TCP proxy server listening on {self.host}:{self.port}; "
            f"worker pool capacity: {self.max_workers}."
        )
        self._publish_metrics()

    def _accept_loop(self):
        while not self._stop_event.is_set():
            listener = self._server_socket
            if listener is None:
                break
            try:
                client_socket, address = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                if not self._stop_event.is_set():
                    self.on_log("Listener socket closed unexpectedly.")
                break

            session_id = uuid.uuid4().hex
            client_socket.settimeout(30)

            with self._clients_lock:
                self._client_sockets[session_id] = client_socket
                self._active_clients += 1

            self.on_session_add(
                session_id,
                str(address[0]),
                "Local" if address[0] in ("127.0.0.1", "::1") else "—",
                "TCP",
                "—",
                "—",
                "Connected",
            )
            self.on_log(f"Client connected: {address[0]}:{address[1]}")
            self._publish_metrics()

            try:
                self._executor.submit(
                    self._handle_client, client_socket, address, session_id
                )
            except RuntimeError:
                self.on_log("Worker pool is shutting down; connection rejected.")
                self._close_client(client_socket, session_id)

    def _handle_client(self, client_socket, address, session_id):
        with self._clients_lock:
            self._active_workers += 1
        self._publish_metrics()

        started = time.perf_counter()
        requested_url = ""
        response_status = "ERROR"
        request_success = False
        downloaded_bytes = 0

        try:
            request = recv_json_frame(client_socket)
            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object")

            # Count the complete application-level request frame (JSON + 4-byte header).
            request_frame_bytes = len(json.dumps(request).encode("utf-8")) + 4
            with self._metrics_lock:
                self._bytes_in += request_frame_bytes

            request_type = request.get("type", "ping")

            with self._metrics_lock:
                self._total_requests += 1

            if request_type == "ping":
                response = {
                    "success": True,
                    "type": "pong",
                    "message": "Connected to Advanced Proxy System",
                    "server_time": datetime.now().isoformat(timespec="seconds"),
                    "server": f"{self.host}:{self.port}",
                }
                response_status = "CONNECTED"

            elif request_type == "fetch":
                requested_url = request.get("url", "")
                response = self._fetch_webpage(requested_url)
                response_status = str(response.get("status", "FETCH ERROR"))
                if response.get("success"):
                    request_success = True
                    downloaded_bytes = int(response.get("size_bytes", 0))
                    with self._metrics_lock:
                        self._successful_requests += 1

            else:
                response = {
                    "success": False,
                    "error": f"Unsupported request type: {request_type}",
                }
                response_status = "BAD REQUEST"

            # Count the complete response frame, including JSON/base64 overhead.
            response_frame_bytes = len(json.dumps(response).encode("utf-8")) + 4
            with self._metrics_lock:
                self._bytes_out += response_frame_bytes
            send_json_frame(client_socket, response)

        except (ConnectionError, socket.timeout) as exc:
            self.on_log(f"Client {address[0]} disconnected: {exc}")
        except Exception as exc:
            self.on_log(f"Request error from {address[0]}: {exc}")
            try:
                error_response = {"success": False, "error": str(exc)}
                error_frame_bytes = len(json.dumps(error_response).encode("utf-8")) + 4
                with self._metrics_lock:
                    self._bytes_out += error_frame_bytes
                send_json_frame(client_socket, error_response)
            except Exception:
                pass
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            if requested_url:
                try:
                    record_request(
                        client_ip=address[0],
                        url=requested_url,
                        status=response_status,
                        latency_ms=elapsed_ms,
                        success=request_success,
                        bytes_downloaded=downloaded_bytes,
                    )
                except Exception as db_exc:
                    self.on_log(f"Database history write failed: {db_exc}")
                self.on_request(requested_url, response_status, elapsed_ms)
            with self._metrics_lock:
                self._total_latency_ms += elapsed_ms
            with self._clients_lock:
                self._active_workers = max(0, self._active_workers - 1)
            self._close_client(client_socket, session_id)
            self._publish_metrics()

    def _fetch_webpage(self, url):
        try:
            parsed = validate_public_http_url(url)
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AdvancedProxySystem/1.0",
                    "Accept": "text/html,application/xhtml+xml",
                },
                method="GET",
            )
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            opener = urllib.request.build_opener(
                SafeRedirectHandler,
                urllib.request.HTTPSHandler(context=ssl_context),
            )

            try:
                with opener.open(request, timeout=FETCH_TIMEOUT) as response:
                    status = response.status
                    content_type = response.headers.get("Content-Type", "")
                    final_url = response.geturl()
                    body = response.read(MAX_BODY_SIZE + 1)
            except urllib.error.HTTPError as exc:
                status = exc.code
                content_type = exc.headers.get("Content-Type", "")
                final_url = exc.geturl()
                body = exc.read(MAX_BODY_SIZE + 1)

            if len(body) > MAX_BODY_SIZE:
                raise ValueError("Webpage exceeds the 5 MB download limit")

            if not (
                "text/html" in content_type.lower()
                or "application/xhtml+xml" in content_type.lower()
            ):
                raise ValueError(
                    f"The URL returned non-HTML content ({content_type or 'unknown type'}). "
                    "Please enter a webpage URL."
                )

            return {
                "success": True,
                "type": "fetch_result",
                "status": status,
                "content_type": content_type,
                "final_url": final_url,
                "body": base64.b64encode(body).decode("ascii"),
                "size_bytes": len(body),
            }

        except Exception as exc:
            self.on_log(f"Fetch failed for {url!r}: {exc}")
            return {
                "success": False,
                "type": "fetch_result",
                "error": str(exc),
            }

    def _close_client(self, client_socket, session_id):
        with self._clients_lock:
            existed = self._client_sockets.pop(session_id, None)
            if existed is not None:
                self._active_clients = max(0, self._active_clients - 1)

        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            client_socket.close()
        except OSError:
            pass

        if existed is not None:
            self.on_session_remove(session_id)
            self.on_log(f"Client session closed: {session_id[:8]}")

    def _publish_metrics(self):
        with self._clients_lock:
            clients = self._active_clients
            workers = self._active_workers
        with self._metrics_lock:
            requests = self._total_requests
            successes = self._successful_requests
            latency_total = self._total_latency_ms
            bytes_in = self._bytes_in
            bytes_out = self._bytes_out

        success_rate = (successes / requests * 100) if requests else 0.0
        avg_latency = (latency_total / requests) if requests else 0.0

        self.on_metrics(
            clients=clients,
            requests=requests,
            threads=workers,
            success_rate=success_rate,
            latency_ms=avg_latency,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
        )

    def stop(self):
        with self._state_lock:
            listener = self._server_socket
            if listener is None:
                return
            self._stop_event.set()
            self._server_socket = None

        try:
            listener.close()
        except OSError:
            pass

        with self._clients_lock:
            active = list(self._client_sockets.items())
        for session_id, client_socket in active:
            self._close_client(client_socket, session_id)

        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

        self.on_status(False, self.host, self.port)
        self.on_log("Proxy server stopped.")
        self._publish_metrics()
