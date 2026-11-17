#!/usr/bin/env python3
"""Log gaze points from the Gaze Tracker websocket to the terminal.

Self-contained: Python 3.8+ standard library only (minimal websocket client included).

Examples:
  python3 gaze_logger.py
  python3 gaze_logger.py --screen-mm 344 222 --interval 50
  python3 gaze_logger.py --json > gaze.jsonl        # one raw snapshot per line
  python3 gaze_logger.py --calibrate                 # trigger calibration, then log

The physical screen size (mm) is NOT reported by the protocol; pass --screen-mm for correct mm values.
"""
import argparse
import base64
import json
import os
import socket
import struct
import sys
import time
from urllib.parse import urlparse


class WebSocket:
    """Minimal RFC 6455 text-frame client (no TLS, no fragmentation of outgoing frames)."""

    def __init__(self, url, timeout=5.0):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET {u.path or '/'} HTTP/1.1\r\nHost: {u.hostname}:{u.port or 80}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("handshake failed")
            resp += chunk
        status_line = resp.split(b"\r\n", 1)[0]
        if b" 101 " not in status_line:
            raise ConnectionError(f"handshake rejected: {status_line!r}")
        self.buf = resp.split(b"\r\n\r\n", 1)[1]
        self.sock.settimeout(None)

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("connection closed")
            self.buf += chunk
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def send(self, obj):
        payload = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self):
        """Return the next text message as a string (handles ping/close)."""
        message = b""
        while True:
            b0, b1 = self._read(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)  # server frames are unmasked
            if opcode == 0x8:
                raise ConnectionError("server closed connection")
            if opcode == 0x9:  # ping -> masked pong
                mask = os.urandom(4)
                self.sock.sendall(bytes([0x8A, 0x80 | len(data)]) + mask +
                                  bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
                continue
            if opcode in (0x1, 0x0):
                message += data
                if b0 & 0x80:
                    return message.decode()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def run(args):
    ws = WebSocket(args.url)
    if args.calibrate:
        ws.send({"type": "start_calibration", "pose": args.pose, "append": args.append})
    ws.send({"type": "start_stream", "interval_ms": args.interval})
    last_ts = None
    try:
        while True:
            msg = json.loads(ws.recv())
            if msg.get("type") != "snapshot":
                if not args.json:
                    print(f"# {json.dumps(msg)}", file=sys.stderr)
                continue
            # The server re-sends the latest snapshot every interval; skip duplicates.
            if msg.get("timestamp_ms") == last_ts and last_ts is not None:
                continue
            last_ts = msg.get("timestamp_ms")
            if args.json:
                print(json.dumps(msg), flush=True)
                continue
            gaze = msg.get("gaze")
            if not gaze:
                print(f"{time.strftime('%H:%M:%S')}  no gaze (not calibrated / no face)", flush=True)
                continue
            sw, sh = msg["screen"]["width_px"], msg["screen"]["height_px"]
            x, y = gaze["x_px"], gaze["y_px"]
            mm_x, mm_y = x / sw * args.screen_mm[0], y / sh * args.screen_mm[1]
            print(f"{msg.get('timestamp_ms')}  px=({x:7.1f},{y:7.1f})  mm=({mm_x:6.1f},{mm_y:6.1f})  "
                  f"screen={sw}x{sh}  source={gaze['source']}", flush=True)
    finally:
        try:
            ws.send({"type": "stop_stream"})
        except OSError:
            pass
        ws.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=os.environ.get("GAZE_WS_URL", "ws://127.0.0.1:8964"))
    p.add_argument("--interval", type=int, default=33, help="stream interval in ms (16..1000)")
    p.add_argument("--screen-mm", type=float, nargs=2, metavar=("W", "H"), default=[344.0, 222.0],
                   help="physical screen size in mm (default: 16-inch MacBook Pro panel)")
    p.add_argument("--json", action="store_true", help="print raw snapshots as JSON lines")
    p.add_argument("--calibrate", action="store_true", help="send start_calibration before streaming")
    p.add_argument("--pose", default="center", help="pose label for --calibrate")
    p.add_argument("--append", action="store_true", help="append to existing calibration samples")
    args = p.parse_args()
    while True:
        try:
            run(args)
        except BrokenPipeError:  # stdout closed (e.g. piped into `head`)
            os._exit(0)
        except (ConnectionError, OSError) as e:
            print(f"# {e}; retrying in 1s (is the Gaze Tracker app running?)", file=sys.stderr)
            time.sleep(1)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
