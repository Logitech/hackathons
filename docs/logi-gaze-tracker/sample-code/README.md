# Gaze Tracker protocol — developer samples

Everything you need to use gaze tracking in **your own application, prototype or agent-generated
code**. The Gaze Tracker app runs in the background and exposes gaze data over a local **websocket carrying JSON**. 
Any language with a websocket client works.

| File | What it is |
| --- | --- |
| [gaze-viewer.html](gaze-viewer.html) | Single-file, dependency-free browser demo: full-screen gaze dot + fixed top-left log of the gaze point in **px** and **mm** from the screen's top-left corner. |
| [gaze_logger.py](gaze_logger.py) | Single-file Python 3.8+ script (stdlib only) that streams gaze points and logs them to the terminal (or as JSON lines). |

## Quick start

1. Start the tracker and calibrate (once per camera/screen setup):
   ```bash
   cd gaze-tracker-electron && npm install && npm start
   ```
   Then trigger calibration via tray icon → **Start Calibration**, or `Ctrl+Alt+G`, or the websocket
   command `start_calibration`. Without calibration you get no gaze (`gaze: null`) unless the
   optional baseline mode is on.
2. Verify the endpoint: `ws://127.0.0.1:8964` (override with env `GAZE_WS_PORT` when starting the app).
3. Run a sample:
   ```bash
   python3 gaze_logger.py --screen-mm 344 222   # terminal log
   open gaze-viewer.html                        # macOS; or just double-click it. Press F for fullscreen
   ```

## Websocket protocol

Connect to `ws://127.0.0.1:8964` and send JSON messages with a `type` field, mirroring the native
tool's protocol:

- `{"type":"get_latest"}` — returns the latest snapshot immediately.
- `{"type":"start_stream","interval_ms":33}` — begins periodic snapshot pushes to this connection
  (the server clamps `interval_ms` to 16–1000; default 33 ≈ 30 Hz). Replies with
  `{"type":"ack","status":"streaming","interval_ms":33}`.
- `{"type":"stop_stream"}` — stops pushes for this connection.
- `{"type":"ping"}` → `{"type":"pong"}`.
- `{"type":"start_calibration","pose":"center","append":false}` — triggers the fullscreen nine-point pass; set `append: true` with another labeled pose after a complete pass to retain samples.
- `{"type":"cancel_calibration"}` — cancels an in-progress calibration.

Other replies: `{"type":"ack","command":...,"status":...}` for calibration commands and
`{"type":"error","message":...}` for bad JSON / unknown commands.

The optional gaze visualization pins off-screen predictions to the nearest visible border
with a red outline. It does **not** clamp or alter the gaze coordinates sent over WebSocket.


### Starting calibration

- **Tray menu**: right-click the tray icon → "Start Calibration".
- **Global shortcut**: `Ctrl+Alt+G` (override with `GAZE_CALIBRATION_SHORTCUT`, Electron accelerator
  syntax) works system-wide, even while the app has no visible window.

During calibration, `Esc` cancels and a click or Space samples the current point. 

## Snapshot reference

Example (abridged) message received on a stream:

```json
{
  "type": "snapshot",
  "timestamp_ms": 123456.7,
  "screen": { "width_px": 1728, "height_px": 1117 },
  "camera": { "width_px": 1280, "height_px": 720 },
  "gaze": { "x_px": 842.1, "y_px": 391.6, "source": "geometric" },
  "comparison": { "legacy": { "x_px": 850.0, "y_px": 400.2 }, "geometric": { "x_px": 842.1, "y_px": 391.6 } },
  "face": { "bounding_box_norm": { "x": 0.3, "y": 0.2, "width": 0.3, "height": 0.4 } },
  "state": { "tracking_enabled": true, "model_calibrated": true, "geometric_calibrated": true, "using_legacy_fallback": false, "using_baseline": false }
}
```

| Field | Notes |
| --- | --- |
| `timestamp_ms` | Millisecond timestamp (monotonic, from the tracker's browser context; not wall-clock). Unchanged timestamp = same frame re-sent by the stream timer, so dedupe on it. |
| `screen.width_px/height_px` | `window.screen` size of the tracked display in **CSS/logical pixels** (points on macOS/HiDPI, not physical device pixels). |
| `gaze` | `null` when there is no prediction (not calibrated, no face detected). Otherwise `x_px`, `y_px` with origin at the screen's **top-left**, x right, y down. Values **can fall outside** `[0,width]×[0,height]` when the user looks off-screen. |
| `gaze.source` | `geometric` (best), `calibrated_legacy_fallback` (+ `fallback_reason`), or `baseline` (uncalibrated, coarse). |
| `comparison`, `geometry`, `provenance` | Optional diagnostics (per-model predictions, eye depth, rejection reasons). Ignore unless you need them. |
| `state` | Tracking/calibration flags and calibration progress (`state.calibration`). |

### Pixels → millimetres

The protocol reports **pixels only** — it does not know the physical size of your screen. To get mm
from the top-left corner, supply the panel's physical size yourself:

```
x_mm = x_px / screen.width_px  * screen_width_mm
y_mm = y_px / screen.height_px * screen_height_mm
```

Both samples use a default of **344 × 222 mm** (16" MacBook Pro panel) which is almost certainly
wrong for your display — set it:

- HTML: `gaze-viewer.html?w_mm=597&h_mm=336` or the **Set screen size** button (persisted in localStorage).
- Python: `--screen-mm 597 336`.

Measure the visible active area, or compute it from the diagonal and aspect ratio.

## Sample: `gaze-viewer.html`

Zero dependencies, no server needed (open with `file://`). It connects, sends `start_stream`,
reconnects automatically if the tracker restarts, and shows:

- a red dot at the gaze point (yellow when the gaze is off-screen and the dot is pinned to the border);
- a large, fixed top-left log: `px`, `mm`, screen size and gaze `source`, plus connection status.

Keys/controls: **F** or the Fullscreen button toggles full-screen (browsers require a user gesture,
so it cannot start fullscreen by itself). Query params: `ws`, `w_mm`, `h_mm`, `interval`.
Drawing assumes the browser is fullscreen on the tracked display; in a window it applies an
approximate offset.

## Sample: `gaze_logger.py`

```bash
python3 gaze_logger.py                       # human-readable log
python3 gaze_logger.py --screen-mm 597 336   # correct mm values
python3 gaze_logger.py --interval 100        # 10 Hz
python3 gaze_logger.py --json > gaze.jsonl   # raw snapshots, one per line
python3 gaze_logger.py --calibrate           # start calibration, then log
python3 gaze_logger.py --url ws://127.0.0.1:9000
```

Sample output:

```
30930.4  px=( 3274.3,  925.9)  mm=( 327.4, 142.7)  screen=3440x1440  source=geometric
```

It includes a small minimal websocket client so it runs on a bare Python install, and
reconnects if the server is not up yet. If you prefer a library, the core is just:

```python
import asyncio, json, websockets  # pip install websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8964") as ws:
        await ws.send(json.dumps({"type": "start_stream", "interval_ms": 33}))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "snapshot" and msg["gaze"]:
                print(msg["gaze"]["x_px"], msg["gaze"]["y_px"])

asyncio.run(main())
```

## Tips for prototypes and coding agents

- Minimal client in any language: connect → send `start_stream` → read `type == "snapshot"` messages → use `gaze.x_px/y_px` (guard for `gaze == null`).
- Always handle reconnects; the tracker may start after your app.
- Gaze is noisy (a few tens of px typical). Smooth it (e.g. exponential moving average, or a median over ~5 samples) and use dwell times (300–800 ms) rather than instantaneous hits for selection.
- Coordinates are in **screen** space, not window space. To map into your window, subtract the window's screen origin (`window.screenX/screenY` + chrome offset in browsers).
- Accuracy depends on calibration; recalibrate if the camera, display, or your seating position changes. A `source` other than `geometric` means reduced quality.
- Use `get_latest` for polling, `start_stream` for continuous data. Multiple clients can connect at the same time.
- The websocket server has no authentication or TLS and is not restricted to localhost in code (it listens on the given port); use a firewall and do not expose it to untrusted networks.
- Requires camera permission for the Gaze Tracker app.
