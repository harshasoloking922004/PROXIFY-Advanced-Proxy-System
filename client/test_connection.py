"""Small TCP handshake test for Advanced Proxy System.

Run the dashboard, click Start Server, then run:
python client/test_connection.py
"""
import socket
import json

HOST = "127.0.0.1"
PORT = 9000


def send_frame(sock, obj):
    payload = json.dumps(obj).encode("utf-8")
    sock.sendall(len(payload).to_bytes(4, "big") + payload)


def recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Server closed connection")
        data.extend(chunk)
    return bytes(data)


def recv_frame(sock):
    size = int.from_bytes(recv_exact(sock, 4), "big")
    if size <= 0 or size > 64 * 1024:
        raise ValueError("Invalid server response size")
    return json.loads(recv_exact(sock, size).decode("utf-8"))


if __name__ == "__main__":
    try:
        with socket.create_connection((HOST, PORT), timeout=5) as sock:
            sock.settimeout(5)
            send_frame(sock, {"type": "ping"})
            response = recv_frame(sock)
        print("SUCCESS: TCP connection established.")
        print(json.dumps(response, indent=2))
    except OSError as exc:
        print(f"CONNECTION FAILED: {exc}")
        print("Start the dashboard and click Start Server first.")
