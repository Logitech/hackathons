#!/usr/bin/env python3
"""Log Hand Tracker telemetry to the terminal.

Self-contained: Python 3.8+ standard library only (includes a tiny WebSocket client).

    python3 hand_tracker_log.py                    # human-readable, one line per hand
    python3 hand_tracker_log.py --raw              # raw JSON, one message per line (pipe to jq, files...)
    python3 hand_tracker_log.py --port 9000        # if config.json uses another websocket_port
    python3 hand_tracker_log.py --changes-only     # skip frames where nothing is detected

The Hand Tracker app must be running (it serves ws://127.0.0.1:<websocket_port>).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import time
from datetime import datetime
from typing import Iterator, Optional, Tuple

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketClient:
    """Minimal RFC 6455 client: text/binary messages, ping/pong, close, fragmentation."""

    def __init__(self, host: str, port: int, path: str = "/", timeout: float = 5.0) -> None:
        self.host, self.port, self.path, self.timeout = host, port, path, timeout
        self.sock: Optional[socket.socket] = None
        self._buffer = b""

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())

        while b"\r\n\r\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server closed the connection during the handshake.")
            self._buffer += chunk
        header, self._buffer = self._buffer.split(b"\r\n\r\n", 1)
        lines = header.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0]:
            raise ConnectionError(f"WebSocket upgrade refused: {lines[0]}")
        headers = {k.strip().lower(): v.strip() for k, v in (l.split(":", 1) for l in lines[1:] if ":" in l)}
        expected = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise ConnectionError("Invalid Sec-WebSocket-Accept from server.")
        self.sock.settimeout(None)  # block while waiting for telemetry

    def _read(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("Connection closed by server.")
            self._buffer += chunk
        data, self._buffer = self._buffer[:count], self._buffer[count:]
        return data

    def _send_frame(self, opcode: int, payload: bytes = b"") -> None:
        # Client-to-server frames must be masked.
        mask = os.urandom(4)
        length = len(payload)
        head = bytes([0x80 | opcode])
        if length < 126:
            head += bytes([0x80 | length])
        elif length < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", length)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", length)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(head + mask + masked)

    def messages(self) -> Iterator[str]:
        """Yield each complete text message until the connection closes."""
        fragments = b""
        while True:
            b0, b1 = self._read(2)
            fin, opcode = bool(b0 & 0x80), b0 & 0x0F
            length = b1 & 0x7F
            if length == 126:
                (length,) = struct.unpack(">H", self._read(2))
            elif length == 127:
                (length,) = struct.unpack(">Q", self._read(8))
            mask = self._read(4) if b1 & 0x80 else None
            payload = self._read(length)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

            if opcode == 0x8:  # close
                try:
                    self._send_frame(0x8, payload[:2])
                except OSError:
                    pass
                return
            if opcode == 0x9:  # ping -> pong
                self._send_frame(0xA, payload)
            elif opcode in (0x1, 0x2, 0x0):  # text / binary / continuation
                fragments += payload
                if fin:
                    message, fragments = fragments, b""
                    yield message.decode("utf-8", errors="replace")

    def close(self) -> None:
        if self.sock:
            try:
                self._send_frame(0x8, struct.pack(">H", 1000))
            except OSError:
                pass
            self.sock.close()
            self.sock = None


def fmt_point(p: dict) -> str:
    return f"({p['x']:.3f}, {p['y']:.3f})"


def log_message(raw: str, args: argparse.Namespace) -> None:
    if args.raw:
        print(raw, flush=True)
        return
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        print(f"! non-JSON message: {raw[:120]}", file=sys.stderr)
        return
    if msg.get("type") != "hand_telemetry":
        return  # ignore message types we don't know about (forward compatibility)

    hands = msg.get("hands", [])
    if args.changes_only and not hands:
        return
    stamp = datetime.fromtimestamp(msg["timestamp_ms"] / 1000).strftime("%H:%M:%S.%f")[:-3]
    if not hands:
        print(f"{stamp}  no hands", flush=True)
        return
    for hand in hands:
        print(
            f"{stamp}  {hand['handedness']:<7} "
            f"thumb={fmt_point(hand['thumb_tip'])} "
            f"index={fmt_point(hand['index_tip'])} "
            f"mid={fmt_point(hand['index_thumb_midpoint'])} "
            f"dist={hand['index_thumb_distance']:.3f}",
            flush=True,
        )


def run(args: argparse.Namespace) -> None:
    while True:
        client = WebSocketClient(args.host, args.port)
        try:
            client.connect()
            print(f"# connected to ws://{args.host}:{args.port}", file=sys.stderr, flush=True)
            for raw in client.messages():
                try:
                    log_message(raw, args)
                except BrokenPipeError:  # e.g. `| head`: stop quietly instead of reconnecting
                    sys.stdout = open(os.devnull, "w")
                    raise SystemExit(0)
            print("# server closed the connection", file=sys.stderr, flush=True)
        except (ConnectionError, OSError) as error:
            print(f"# {error}", file=sys.stderr, flush=True)
        finally:
            client.close()
        if args.no_reconnect:
            return
        print(f"# reconnecting in {args.retry_seconds:g}s (Ctrl+C to quit)...", file=sys.stderr, flush=True)
        time.sleep(args.retry_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log Hand Tracker telemetry to the terminal.")
    parser.add_argument("--host", default="127.0.0.1", help="default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="websocket_port from config.json (default: 8765)")
    parser.add_argument("--raw", action="store_true", help="print raw JSON messages instead of a summary")
    parser.add_argument("--changes-only", action="store_true", help="skip messages with no hands detected")
    parser.add_argument("--no-reconnect", action="store_true", help="exit instead of reconnecting")
    parser.add_argument("--retry-seconds", type=float, default=2.0, help="reconnect delay (default: 2)")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        run(parse_args())
    except KeyboardInterrupt:
        pass
