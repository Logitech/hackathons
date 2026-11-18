# Logi Hands Tracker – Developer Guide & Samples

Build your own hand-tracking prototypes on top of [**Logitech Hands Tracker**](https://github.com/Logitech/hackathons/releases/tag/hands-tracker).
The app is designed for the LogiInsight hackathon webcam (`LVNext CPD Camera`), runs MediaPipe Hand Landmarker, and **streams hand positions as JSON over a
local WebSocket**. Any language that can open a WebSocket (browser JS, Python, Node, Unity, Rust, …)
can consume it. It can also serve the latest camera frame as a PNG over HTTP.


## Installing Hands Tracker (Windows & macOS)

Download the installer for your platform from the
[**Logitech Hands Tracker Release**](https://github.com/Logitech/hackathons/releases/tag/hands-tracker):
the `.exe` installer for Windows, or the `.dmg` for macOS (pick the Intel or Apple Silicon/arm64 build
matching your Mac).

The builds are **unsigned**, so Windows and macOS will warn you once on first launch. The app runs
fully locally and needs **camera** permission.

### macOS

1. Open the `.dmg` and drag **Hand Tracker** onto **Applications**.
2. Launch it from Applications. macOS blocks it the first time with a *"Not Opened"* dialog.
   Click **Done** (not *Move to Bin*).
3. Open **System Settings → Privacy & Security**, scroll to **Security** and click **Open Anyway**
   next to *"Hand Tracker" was blocked*.
4. Confirm with **Open Anyway** (you may be asked for your password), then allow **camera** access
   when prompted.
5. The app lives in the menu bar (tray icon).

If macOS still refuses to open the app (e.g. it reports the app as damaged), remove the quarantine
flag from a terminal and launch it again:

```bash
xattr -cr "/Applications/Hand Tracker.app"
```

### Windows

1. Run the installer.
2. If SmartScreen shows *"Windows protected your PC"*, click **More info → Run anyway** and accept
   installing the unsigned software.
3. Allow camera access when asked. The app lives in the system tray.

## Quick start

| File | What it is |
|------|------------|
| [`hand-viewer.html`](./hand-viewer.html) | Single-file, zero-dependency full-screen viewer. Draws and labels the thumb, index, midpoint and hand. |
| [`hand_tracker_log.py`](./hand_tracker_log.py) | Single-file Python 3.8+ script (standard library only) that logs telemetry to the terminal. |

1. Start Hand Tracker (installed app as above). Make sure `camera_name` in `config.json` matches your camera, this file is in the installed folder and depends on our OS.
2. Pick a sample:
   - **Browser**: double-click `hand-viewer.html` (or `open hand-viewer.html`). Press `F` for full screen.
   - **Terminal**: `python3 hand_tracker_log.py`
3. Move your hand in front of the camera.

If `websocket_port` in `config.json` is not `8765`, pass it: `?port=9000` for the HTML,
`--port 9000` for Python.

## Protocol reference

### Endpoints

Everything is served from one loopback-only port, `websocket_port` in `config.json` (default `8765`).

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `ws://127.0.0.1:<port>` | WebSocket | Telemetry stream (publish-only). |
| `http://127.0.0.1:<port>/api/frame` | `GET` | Latest unannotated camera frame (PNG). |
| `http://127.0.0.1:<port>/desktop-view/` | `GET` | Built-in demo page for `/api/frame`. |

- The server binds to `127.0.0.1` only: clients must run on the same machine.
- No authentication, no TLS (`ws://`, not `wss://`). No CORS/Origin restrictions, so web pages
  (including `file://` pages) can connect directly.
- The WebSocket path is ignored: `ws://127.0.0.1:8765` and `ws://127.0.0.1:8765/anything` are equivalent.
- The stream is **one-way**. Anything a client sends is ignored.
- Any number of clients may connect at once; each receives every message.

### Message: `hand_telemetry`

One text message (JSON) is sent **per processed camera frame** (roughly the camera frame rate,
~30 msg/s), **including frames with no hands** (`hands` is then `[]`). Clients that connect
mid-stream just start receiving from the next frame; there is no history or handshake message.

```json
{
  "type": "hand_telemetry",
  "timestamp_ms": 1794923182167,
  "image": {
    "width": 1024,
    "height": 768,
    "coordinate_space": "normalized_mirrored"
  },
  "hands": [
    {
      "handedness": "Right",
      "thumb_tip":            { "x": 0.677, "y": 0.411 },
      "index_tip":            { "x": 0.705, "y": 0.461 },
      "index_thumb_midpoint": { "x": 0.691, "y": 0.436 },
      "index_thumb_distance": 0.057
    }
  ]
}
```

#### Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"hand_telemetry"`. Ignore messages with other types (forward compatibility). |
| `timestamp_ms` | number | Capture time in **Unix epoch milliseconds** (`Date.now()` on the tracker machine). |
| `image.width`, `image.height` | number | Size in pixels of the processed camera area the coordinates refer to. Default is `1024 × 768` (the crop used for the LVNext CPD Camera), or the full frame when `camera_resolution` is set in `config.json`. Use it for the aspect ratio. |
| `image.coordinate_space` | string | Currently always `"normalized_mirrored"` (see below). |
| `hands` | array | 0–2 hand objects (the tracker is configured for at most two hands). |

#### Hand object

| Field | Type | Description |
|-------|------|-------------|
| `handedness` | `"Left"` \| `"Right"` \| `"Unknown"` | Label from MediaPipe's classifier. |
| `thumb_tip` | `Point` | Tip of the thumb (MediaPipe landmark 4). |
| `index_tip` | `Point` | Tip of the index finger (MediaPipe landmark 8). |
| `index_thumb_midpoint` | `Point` | Midpoint between `thumb_tip` and `index_tip`. A good "cursor" for pinch interactions. |
| `index_thumb_distance` | number | Euclidean distance between the two tips, in normalized units. Small values = pinch. |

`Point` is `{ "x": number, "y": number }`.

> **Only thumb and index tips are published.** The other fingers and the full 21-landmark skeleton are
> *not* part of the protocol (they are used for the preview window only). Design prototypes around
> thumb/index/pinch interactions.

### Coordinate space: `normalized_mirrored`

- `x` and `y` are in **[0, 1]** (clamped).
- **x** grows **left → right** as the user sees a *mirror* of themselves (the camera x axis is already flipped).
- **y** grows **bottom → top**: `y = 0` is the **bottom** of the image, `y = 1` the **top**.
  This differs from canvas/screen coordinates; convert with `screenY = (1 - y) * height`.
- Normalization is per axis, so a distance of `0.1` is `0.1 × image.width` horizontally but
  `0.1 × image.height` vertically. For true pixel distances, scale first:
  `dx = (a.x - b.x) * image.width`, `dy = (a.y - b.y) * image.height`.

Mapping to a screen / canvas of size `W × H`:

```js
const screen = (p) => ({ x: p.x * W, y: (1 - p.y) * H });
```

### Behaviour notes & gotchas

- **Hand order is not stable.** Identify hands by `handedness`, never by array index.
- **Two hands may share a label.** The classifier can occasionally label both hands `"Right"` (or
  `"Left"`). Don't assume at most one hand per label.
- **Handedness may look swapped.** The label comes straight from MediaPipe, which assumes a mirrored
  (selfie) image. Depending on how your camera is mounted, "Left" may be the user's right hand.
  Test once and swap in your client if needed.
- **Smoothing.** With `hand_smoothing.enabled` (default), tip positions are exponentially smoothed
  per handedness label (`alpha` 0.35, reset after 250 ms without that hand). `index_thumb_midpoint` and
  `index_thumb_distance` are computed from the smoothed points. Set `enabled: false` in
  `config.json` for raw positions (more jitter, less lag).
- **No hand ⇒ empty array, not silence.** Detect "hand lost" via `hands.length === 0` or by a
  stale `timestamp_ms` / no messages. If the app stops, the socket closes.
- **Reconnect.** Clients should reconnect with a short delay (both samples do).
- **Latency.** Typical end-to-end latency is the camera frame time plus inference (tens of ms).
  Use `timestamp_ms` if you need to measure it (same machine, same clock).

### HTTP: `GET /api/frame`

Returns the latest **full, unannotated camera frame** as a PNG (the whole capture, not the cropped
tracking area).

| Status | Meaning |
|--------|---------|
| `200` | `Content-Type: image/png`, header `X-Frame-Timestamp` (ISO-8601), `Cache-Control: no-store`. |
| `429` | Too many frame requests in flight (max 4). |
| `405` | Method other than `GET`. |
| `503` | Camera capture not available (yet). |
| `504` | The renderer didn't answer within 5 s. |

Errors are JSON: `{ "error": "message" }`. Each request encodes a PNG, so poll sparingly
(a few Hz, not per telemetry message).

```js
const res = await fetch("http://127.0.0.1:8765/api/frame", { cache: "no-store" });
const bitmap = await createImageBitmap(await res.blob());
```

```bash
curl -o frame.png http://127.0.0.1:8765/api/frame
```

### Configuration that affects clients (`config.json`)

| Key | Default | Effect on clients |
|-----|---------|-------------------|
| `websocket_port` | `8765` | Port for WebSocket and HTTP. |
| `hand_smoothing.enabled` / `alpha` / `reset_after_ms` | `true` / `0.35` / `250` | Smoothing of tip positions (see above). |
| `camera_resolution` | _(unset)_ | When set, `image.width/height` equal the full frame instead of the default 1024×768 crop. |

Restart the app after editing `config.json`.

## Sample 1: `hand-viewer.html`

A single HTML file, no build, no libraries. It connects to the WebSocket, draws each hand full-screen
and labels every point:

- `Left · Thumb` / `Left · Index` (and `Right · …`) at the fingertips
- `Left hand` / `Right hand` at the thumb–index midpoint, with the distance and a `PINCH` flag when
  `index_thumb_distance < 0.06`
- Different color per hand, status HUD (connection, hands detected, msg/s)

Options:

| URL parameter | Meaning |
|---------------|---------|
| `?port=9000` | Use another `websocket_port`. |
| `?host=…` | Tracker host (default `127.0.0.1`). |
| `?url=ws://…` | Full WebSocket URL override. |
| `?stretch=1` | Fill the window instead of keeping the camera aspect ratio. |

Keys: `F` (or double-click) full screen · `S` toggle stretch · `H` toggle HUD.

Minimal client you can copy into any page:

```html
<script>
  const ws = new WebSocket("ws://127.0.0.1:8765");
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type !== "hand_telemetry") return;
    for (const hand of msg.hands) {
      console.log(hand.handedness, hand.index_thumb_midpoint, hand.index_thumb_distance);
    }
  };
</script>
```

## Sample 2: `hand_tracker_log.py`

Requires **Python 3.8+ and nothing else** (it ships a small RFC 6455 WebSocket client).

```bash
python3 hand_tracker_log.py                  # one line per hand
python3 hand_tracker_log.py --raw            # raw JSON, one message per line
python3 hand_tracker_log.py --changes-only   # hide "no hands" lines
python3 hand_tracker_log.py --port 9000      # custom websocket_port
```

Output (status messages go to stderr, data to stdout, so piping is clean):

```text
# connected to ws://127.0.0.1:8765
14:46:21.930  Left    thumb=(0.277, 0.411) index=(0.305, 0.461) mid=(0.291, 0.436) dist=0.057
14:46:21.930  Right   thumb=(0.677, 0.411) index=(0.705, 0.461) mid=(0.691, 0.436) dist=0.056
14:46:21.963  no hands
```

Flags: `--host`, `--port`, `--raw`, `--changes-only`, `--no-reconnect`, `--retry-seconds`.
It reconnects automatically if the tracker is not running yet or restarts. `Ctrl+C` exits.

Examples:

```bash
python3 hand_tracker_log.py --raw > session.jsonl           # record a session
python3 hand_tracker_log.py --raw | jq '.hands[].index_thumb_distance'
```

Using it as a library — import and iterate:

```python
from hand_tracker_log import WebSocketClient
import json

client = WebSocketClient("127.0.0.1", 8765)
client.connect()
for raw in client.messages():
    msg = json.loads(raw)
    for hand in msg["hands"]:
        if hand["index_thumb_distance"] < 0.06:
            print("pinch!", hand["handedness"], hand["index_thumb_midpoint"])
```

## Recipes & ideas

- **Pinch to click/drag**: treat `index_thumb_distance` below a threshold (e.g. `0.06`) as "pressed".
  Use hysteresis (press `< 0.05`, release `> 0.08`) to avoid flicker.
- **Air cursor**: map `index_thumb_midpoint` to the screen with `screenY = (1 - y) * H`.
- **Two-hand gestures**: pick the `Left` and `Right` hands by label; scale/rotate with the vector between their midpoints.
- **Sliders/knobs**: use `index_thumb_distance` as a continuous 0–1-ish control.
- **Camera-assisted apps**: pair telemetry with `GET /api/frame` to run your own CV/ML on the image.
- **Bridging**: forward messages to MIDI/OSC/HTTP, game engines, or LLM agents; it's just JSON lines.

## Notes for AI agents / code generators

- Connect to `ws://127.0.0.1:8765` (no handshake or subscription message needed), `JSON.parse` each message,
  and filter on `type === "hand_telemetry"`.
- Treat the schema above as the complete, authoritative contract. Do not invent landmark fields.
- Remember `y` is bottom-up and `x` is mirrored; flip `y` for canvas/screen rendering.
- Handle `hands: []`, reconnects, and 1–2 hands.
- For testing without a camera, run a small WebSocket server that emits the example message above
  at ~30 Hz and point the client at it with `--port` / `?port=`.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Connection refused / "Connecting…" | Is Hand Tracker running? Does the port match `websocket_port`? (`curl -i http://127.0.0.1:8765/api/frame` should answer.) |
| Connected, but always `no hands` | Hand fully visible, good light; camera correct (`camera_name`) and not used by another app. |
| Labels swapped Left/Right | See "Handedness may look swapped". |
| Jittery points | Enable `hand_smoothing` or increase smoothing (lower `alpha`). |
| Port already in use | Change `websocket_port` in `config.json` and restart the app. |
