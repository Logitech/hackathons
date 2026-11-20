# LogiInsight Webcam — PC SDK API Reference

**SDK version 1.5.1** · for the LogiInsight hackathon webcam

> The AI features described here exist **only on the LogiInsight webcam** (the AI runs inside
> it). With another webcam (MX Brio, your own, a laptop's built-in camera) only the plain
> video parts apply.

Quick start and installation: the [quick start](./) page, or `README.md` in the [SDK zip](https://github.com/Logitech/hackathons/releases/download/logiinsight-sdk-v1.5.1/logiinsight_api_sdk_v1.5.1.zip).

Contents

1. [Architecture](#1-architecture)
2. [Video streams](#2-video-streams)
3. [The near-infrared (IR) stream](#3-the-near-infrared-ir-stream)
4. [Coordinate systems](#4-coordinate-systems)
5. [Python API — `LogiWebcamClient`](#5-python-api--logiwebcamclient)
6. [Python API — `camera_utils`](#6-python-api--camera_utils)
7. [AI output JSON](#7-ai-output-json)
8. [AI configuration (INI)](#8-ai-configuration-ini)
9. [YUV snapshot](#9-yuv-snapshot)
10. [Examples and limits](#10-examples-and-limits)
11. [Audio (USB microphone)](#11-audio-usb-microphone)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Architecture

One USB-C cable carries three kinds of traffic:

| Interface | Protocol | Carries |
|---|---|---|
| **UVC** (USB Video Class) | standard webcam drivers on every OS | video: the RGB stream and the near-infrared stream |
| **USB NCM** | virtual Ethernet adapter → SSH/SFTP at `192.168.1.10:22` | AI result JSON, AI configuration (INI), optional YUV snapshots |
| **UAC** (USB Audio Class) | standard audio drivers on every OS | the microphone input, 2 channels (§11) |

Video and audio need no setup. **AI data and configuration need the network link**, which
needs a manual address on your PC (`192.168.1.20/24`, no gateway; see the README).

```
 camera ──USB-C──┬── UVC  ──►  cv2.VideoCapture      (RGB, IR)
                 ├── UAC  ──►  sounddevice           (microphone)
                 └── NCM  ──►  LogiWebcamClient (SSH/SFTP): JSON · INI · YUV
```

The camera runs face detection and an optional 478-point face mesh on the device. It
**only runs while the RGB camera is open as an MJPG stream**; with no reader (or a
non-MJPG stream) the result file simply stops changing.

### Files visible over SFTP

The SSH user sees only this sandbox:

| Path | Content |
|---|---|
| `/files/logi_conf/logiwebcam_ai.ini` | AI settings (read/write) |
| `/files/logi_conf/logiwebcam_ai_output.json` | latest AI results |
| `/files/logi_conf/logiwebcam_frame.yuv` | optional paired NV12 frame |
| `/files/logi_conf/logiwebcam_frame.status` | one-line result of the last YUV write |
| `/files/LogiApp.log` | the camera application's log (read-only use; helpful when something fails) |

The SSH user name and password are on the card in your kit. Never put them in code or
commit them: export `LOGIWEBCAM_USER` and `LOGIWEBCAM_PASSWORD` (or pass `--user` /
`--password`). `python check_connection.py` tests the whole link step by step.

---

## 2. Video streams

The camera appears to the host as UVC cameras (the name prefix is the product name,
`LVNext` by default):

| UVC camera | Sensor | Formats | Use |
|---|---|---|---|
| `LVNext Camera` | RGB | MJPG, YUY2, NV12 | RGB video and the AI |
| `LVNext CPD Camera` | near-infrared (monochrome) | **MJPG only**, portrait | IR video — `example_IR.py` |
| `LVNext Hello Camera` | Windows Hello stream | 8-bit, 480×480 only | not used by this SDK; camera apps cannot open it, ignore it |

The camera is also a USB
microphone (`LVNext Microphone`, §11), so camera apps list it next to the cameras.

OS camera *indexes* (the number you give to `cv2.VideoCapture`) are **not fixed**: they
depend on the OS, the backend and what else is plugged in. On Linux the V4L2 card name
(`/sys/class/video4linux/video*/name`) identifies each stream; elsewhere probe the
indexes (`camera_utils.list_cameras()`) or pass `--device`. Each UVC camera also creates
an extra metadata node on Linux that cannot deliver frames; ignore it.

### RGB camera — advertised modes (maximum frame rate)

Rates depend on the USB link speed; every mode also offers lower rates down to 5 fps.

| Format | SuperSpeed (USB 3) | High Speed (USB 2) | Full Speed |
|---|---|---|---|
| **MJPG** | 640×480@240 · 1280×720@240 · 1920×1080@120 · 3840×2160@60 | 640×480@60 · 1280×720@60 · 1920×1080@30 | 640×480@30 |
| YUY2 | 640×480@240 · 1280×720@120 · 1920×1080@60 · 3840×2160@15 | 640×480@60 · 1280×720@60 · 1920×1080@15 | 640×480@15 |
| NV12 | 640×480@60 · 1280×720@60 · 1920×1080@60 · 3840×2160@30 | 640×480@60 · 1280×720@60 · 1920×1080@15 | 640×480@15 |

These are upper bounds. Actual rates depend on exposure (low light lowers the frame
rate), your USB controller and the OS backend. Use a USB 3 port and cable for 1080p and
above.

### Opening the RGB stream correctly

```python
import cv2

cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)      # Windows; CAP_V4L2 Linux; CAP_AVFOUNDATION macOS
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)           # 1. size FIRST
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # 2. then the format
```

* **Order: size, then fps, then FOURCC.** On DirectShow, setting the FOURCC first, or
  requesting an fps after it, silently gives YUY2 on the RGB camera. The AI only runs on
  MJPG, so always check the negotiated format.
* **The AI needs MJPG.** On YUY2 or NV12 the JSON stops updating, with no error.
* **Windows MSMF and macOS AVFoundation** frequently ignore the FOURCC request. Read it
  back (`cap.get(cv2.CAP_PROP_FOURCC)`); `rgb_ai_capture.py` does and warns. On Windows the
  DirectShow backend (`CAP_DSHOW`) honours it more reliably.
* Keep a reader running (`cap.read()` in a loop). The AI runs only while the RGB stream
  is open.

---

## 3. The near-infrared (IR) stream

### What it is

* A **monochrome** sensor (no colour filter) that responds to a **wide range of
  near-infrared wavelengths**. The camera also has a near-infrared illuminator that is on
  while the IR stream is open. Expect the image to look different from RGB: skin and many
  dark fabrics are bright, screens may be dark, sunlight adds a lot of infrared.
* The picture is **grey** and **portrait**.

### The CPD stream (what this SDK uses)

`LVNext CPD Camera` delivers **MJPG**, so every OS and OpenCV backend can open it:

| Link speed | 256×320 | 512×640 | 1024×1280 |
|---|---|---|---|
| SuperSpeed (USB 3) | 240 fps max | 240 fps max | 120 fps max |
| High Speed (USB 2) | 240 fps max | 60 fps max | 15 fps max |
| Full Speed | 60 fps max | 15 fps max | — |

256×320 is the default when no size is requested. As for RGB, these are advertised limits.
The examples ask for 512×640 at 30 fps.

### Reading it

```python
import cv2
from camera_utils import find_camera, open_camera, backend_id

index, backend_name = find_camera("ir")           # by name on Linux, by probing elsewhere
cap, info = open_camera(index, backend_id(backend_name), 512, 640, "MJPG", 30)
ok, frame = cap.read()                            # numpy.ndarray, shape (640, 512, 3), uint8
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)    # single channel (640, 512), uint8
cap.release()
```

OpenCV decodes the MJPG into a three-channel BGR array whose channels are identical;
convert to one channel with `cv2.cvtColor(..., COLOR_BGR2GRAY)`.

### Processing in `example_IR.py`

`raw`, `stretch` (1st–99th percentile contrast stretch), `clahe` (adaptive histogram
equalisation), `threshold` (fixed), `otsu` (automatic). The functions `to_gray`,
`contrast_stretch`, `clahe_enhance`, `fixed_threshold`, `otsu_threshold` and `process`
are plain functions on `uint8` arrays that you can import.

### Good to know

* **The AI JSON never describes the IR picture.** It is computed from the RGB stream only.
* **The first ~20 frames after opening the IR stream are an auto-exposure ramp** (very
  bright, then dark, then settled). Skip them before you process frames.
* If the IR picture flickers, use `example_IR.py --flicker-filter` (per-pixel maximum of
  two consecutive frames).
* **RGB and IR at the same time.** You can open both streams together and close them in
  any order. The frame rate is the limit:
  * both streams MJPG (the only way to keep the AI running): each stream typically runs at
    about 15 fps, or the IR stream drops to about 1 fps while RGB keeps about 29 fps;
  * RGB as NV12 or YUY2 and IR as MJPG: both streams run at 30 fps, but the AI is off,
    because it only runs on an MJPG RGB stream.

  Open the RGB stream first.

---

## 4. Coordinate systems

| Space | Size | Used for |
|---|---|---|
| **Stream (preview) pixels** | the resolution of the RGB stream you opened, e.g. 1920×1080 | **every bbox and every landmark in the AI JSON**; the YUV snapshot has this size |
| **IR stream pixels** | 256×320, 512×640 or 1024×1280 (portrait) | the IR image only; no AI data refers to it |

Therefore:

* `faces[i].bbox` and `faces[i].landmarks` are absolute pixels of the **RGB stream you are
  reading**. Draw them directly on the frame from `cap.read()`. If you resize the frame,
  scale the coordinates by `new_size / stream_size`.
* The **face mesh is absolute too**: do not rescale it onto the face box.
* Face `z` is relative depth in the same units as `x` and `y`.
* Origin is the top-left corner, `x` to the right, `y` down.
* The frame size from `cap.read()` is the size the OS negotiated with the camera
  (`rgb_ai_capture.py` prints it).

---

## 5. Python API — `LogiWebcamClient`

```python
from logiwebcam import LogiWebcamClient, LogiWebcamConnectionError, LogiWebcamDataError, __version__
```

Requires only `paramiko` to import. `numpy` and `cv2` are imported lazily, inside
`get_device_snapshot()`.

### Constructor

```python
LogiWebcamClient(ip="192.168.1.10", username=None, password=None, port=22, timeout=10)
```

If `username` or `password` is `None`, the `LOGIWEBCAM_USER` / `LOGIWEBCAM_PASSWORD`
environment variable is used; if either is still missing, `ValueError` is raised. Both
values are on the card in your kit.

### Connection

| Member | Description |
|---|---|
| `connect()` | Opens SSH. Idempotent. Raises `LogiWebcamConnectionError` (wrong address/adapter, wrong password, timeout 10 s). |
| `disconnect()` | Closes SFTP and SSH. Idempotent. |
| `is_connected` | **Property**, `True` while the SSH transport is active. |
| `with LogiWebcamClient() as cam:` | `connect()` on entry, `disconnect()` on exit. |

There is no automatic reconnect: after a USB unplug, create a new client.

### Configuration

```python
cam.set_ai_config(
    enable_face_detection=True,
    enable_face_mesh=False,        # needs face detection on, else forced off
    enable_debug_timestamp=False,  # kept for compatibility; has no visible effect
    enable_yuv_snapshot=False,     # write a paired NV12 file each cycle
) -> bool
```

Writes the INI file. The camera re-reads it **about twice a second** while streaming
(not instantly): wait ≈ 0.5–1 s after changing a flag. The returned `True` means the
write command was issued, not that the camera has applied it; check the JSON.

### Reading results

| Call | Returns |
|---|---|
| `get_latest_ai_data()` | `dict` (see [§7](#7-ai-output-json)) or `None` if missing / empty / being rewritten |
| `get_yuv_status()` | one-line status string of the last snapshot write, or `None` |
| `get_device_snapshot(retries=3, verbose=False)` | `(bgr_ndarray, data)`; `(None, None)` if no JSON; `(None, data)` if no YUV is being written |
| `diagnose()` | prints and returns a dict of INI/JSON/YUV probes. Run this first when results stay `None` |
| `get_firmware_version()` | first line of the camera's version text (`… hackathon-1.5.1 <variant> <commit>`), or `None` |

`get_device_snapshot()` fetches the JSON and the YUV file, checks that the timestamp in
the JSON equals the 8-byte header of the YUV, retries on mismatch and converts NV12 → BGR
with OpenCV.

Module helpers: `firmware_matches_sdk(text)` (`True`/`False`/`None` = unknown) compares the
firmware release with the SDK's major.minor version. `AiStalenessMonitor(max_age_s=2.0)`
has one method, `update(data)`: call it with every result of `get_latest_ai_data()`; it returns
a warning text **once** when `timestamp_ms` stopped changing for `max_age_s` seconds (the RGB
stream is not MJPG, or nobody reads it), otherwise `None`. The RGB examples use both.

Exceptions: `LogiWebcamConnectionError`, `LogiWebcamDataError`, and `ValueError` for a
missing password.

---

## 6. Python API — `camera_utils`

Video-side helpers (no SSH), used by `example_IR.py`.

| Function | Purpose |
|---|---|
| `uvc_backends()` | OpenCV backends per OS: V4L2 (Linux); DSHOW then MSMF (Windows); AVFoundation (macOS) |
| `open_camera(index, backend=None, width=None, height=None, fourcc="MJPG", fps=None)` → `(cap, info)` | Opens with size, then fps, then FOURCC set (the order DirectShow needs to keep MJPG); `info` holds the *negotiated* `width`, `height`, `fourcc`, `fps`, `backend`. Raises `CameraNotFoundError` |
| `list_cameras(max_index=10, probe_size=None)` | Probes indexes; list of dicts (`index`, `backend`, `name` (Linux), `width`, `height`, `fourcc`, `gray`) |
| `find_camera(kind)` | `kind="rgb"` or `"ir"` → `(index, backend_name)`. Linux: by name. Windows/macOS: by probing (portrait or perfectly grey frame ⇒ IR). A laptop's built-in webcam can be mistaken for the RGB camera: pass `--device` |
| `backend_id(name)` | name → OpenCV backend constant |
| `is_grayscale(frame)` | cheap "this is the IR picture" test |
| `describe(info)` | one-line description of an `open_camera` result |
| `install_stop_flag()` → `StopFlag` | Ctrl+C / SIGTERM set a flag instead of raising; a second Ctrl+C raises `KeyboardInterrupt` |
| `camera_hint()` | OS-specific checklist used in error messages |
| `CameraNotFoundError` | raised when no usable camera exists |

Standard exit pattern used by every script:

```python
stop = install_stop_flag()
cap, info = open_camera(...)
try:
    while not stop.is_set():
        ok, frame = cap.read()
        ...
except KeyboardInterrupt:
    pass
finally:
    cap.release()
    cv2.destroyAllWindows()
```

---

## 7. AI output JSON

File: `/files/logi_conf/logiwebcam_ai_output.json`, written atomically (temp file then
rename) for every processed frame. The AI result rate is lower than the video frame rate,
so consecutive video frames can share a result (at 30 fps video, expect about 27–30
results per second).

```json
{
  "api_version": 2,
  "plugin_loaded": true,
  "timestamp_ms": 1812345678,
  "face_timestamp_ms": 1812345678,
  "faces": [
    { "bbox": [x, y, w, h], "confidence": 0.97,
      "capture_timestamp_ms": 1812345678,
      "landmarks": [[x, y, z], "... 478 points when the mesh is on"] }
  ]
}
```

(The timestamp value above is illustrative.)

| Field | Meaning |
|---|---|
| `api_version` | JSON schema version, the integer `2`; always present, also when `plugin_loaded` is `false` |
| `plugin_loaded` | `true` while the AI runs. `false` means empty `faces`: treat it as "no AI results", not an error (stream not open, wrong format, or the AI restarted) |
| `timestamp_ms` | One value per processed frame, taken when the frame reaches the AI, **before** inference. It is the camera's **wall clock** in milliseconds (the camera may have no real-time clock, so it can start at an arbitrary date and jump), stored in a **32-bit** value, so it wraps. Use it only to compare with other values from the same camera, for example to see that results advance or to pair the YUV file, never as absolute time |
| `face_timestamp_ms`, `faces[i].capture_timestamp_ms` | Always equal to `timestamp_ms` |
| `faces[i].bbox` | `[x, y, width, height]`, **stream pixels** (§4) |
| `faces[i].confidence` | score 0…1 |
| `faces[i].landmarks` | empty unless `enable_face_mesh`. **Even with the mesh on it is empty in some results** (it was present in roughly half to most results, less while the head moves), so check its length before use. When present: 478 `[x, y, z]` in stream pixels (MediaPipe face-mesh topology, including 10 iris points at 468–477). `z`: relative depth in `x`/`y` units |
| `yuv_*` | present only with the YUV snapshot ([§9](#9-yuv-snapshot)) |

* **At most one face** per result.
* Ignore keys you do not know.

---

## 8. AI configuration (INI)

File `/files/logi_conf/logiwebcam_ai.ini`, section `[logiwebcam_ai]`. Created with
defaults on first start; re-read about every 0.5 s while streaming, so changes apply
without restarting the stream.

| Key | Default | Meaning |
|---|---|---|
| `enable_face_detection` | `1` | face box and score |
| `enable_face_mesh` | `0` | 478-point mesh; forced to `0` if face detection is off |
| `enable_debug_timestamp` | `0` | kept for compatibility; the camera no longer draws anything on the video |
| `enable_yuv_snapshot` | `0` | write the NV12 frame next to the JSON ([§9](#9-yuv-snapshot)) |

`set_ai_config()` writes all four keys at once; keys you do not pass fall back to the
defaults shown in its signature (so it turns `enable_face_detection` **on** unless you
pass `False`).

**To switch the built-in AI off** write `enable_face_detection=False` and
`enable_face_mesh=False`: the camera then runs no AI model; the JSON keeps updating but
`faces` stays empty. Opening the RGB camera as YUY2 or NV12 instead of MJPG also stops the
AI, but then the JSON stops updating altogether (the AI only runs on MJPG).

---

## 9. YUV snapshot

### Why the live picture and the JSON can differ

The video reaches you over USB (UVC); the AI JSON is a file you fetch over SSH/SFTP. They
are two separate paths with no shared frame number, and the AI analyses a frame while newer
ones are already streaming. If you draw the latest JSON on the frame you just read, the boxes
and landmarks can therefore lag a moving face. This is expected. The camera draws nothing on
the video, so every box you see comes from this JSON.

`enable_yuv_snapshot=True` makes the camera write the exact frame its models saw, so
image and results are guaranteed to belong together. That picture is the frame the AI
analysed, not necessarily the frame the live video showed at that moment, so the live image
and the snapshot of the same instant can look different.

* File: `/files/logi_conf/logiwebcam_frame.yuv` = 8-byte little-endian `uint64`
  timestamp, then raw **NV12** (Y plane, then interleaved UV).
* The JSON gains: `yuv_capture_timestamp_ms`, `yuv_path`, `yuv_pixel_format` (`"NV12"`),
  `yuv_width`, `yuv_height`, `yuv_stride_y`, `yuv_stride_uv`, `yuv_header_size` (`8`),
  `yuv_total_size`, `yuv_ok_count`.
* `logiwebcam_frame.status`: `ok ts_ms=… size=… count=…` or `err stage=… errno=… …`
  (`errno=28` means the partition is full).
* Size is the stream size: about **3.1 MB** per frame at 1920×1080 (0.46 MB at 640×480),
  and up to twice that on disk during a write. The camera's storage has only a few MB
  free: **enable it only while you capture and switch it off afterwards**
  (`rgb_ai_capture.py --device-snapshot` does this in its `finally` block).
* The JSON and the YUV are two files. `get_device_snapshot()` compares the timestamps and
  retries (3 times by default); an occasional retry message is normal at high frame rates.
* The YUV is the plain camera frame; the examples draw the boxes onto it from the JSON.
* The per-frame `frame_NNNN.json` files that `rgb_ai_capture.py` writes are not the raw camera
  JSON: they wrap it under `device_ai_data` next to host-side fields (`frame_index`,
  `host_timestamp`, `host_time_iso`, `image_file`, `image_resolution`, `fetch_latency_ms`
  or `capture_latency_ms`).
* A snapshot takes about 2 s to fetch over SFTP at 1920×1080, so plan for roughly one
  snapshot every 2 s.

---

## 10. Examples and limits

| Script | What it does | Notes |
|---|---|---|
| `rgb_ai_capture.py` | Captures N RGB frames, fetches the JSON per frame (or snapshot pairs with `--device-snapshot`), draws face box and mesh, saves `frame_NNNN.png` + `.json` | `--frames`, `--interval`, `--width`, `--height`, `--face-mesh`, `--device-snapshot`, `--ip`, `--user`, `--password`, `--device` |
| `rgb_ai_live.py` | The same overlays live in a window | lists the cameras and asks which to use if `--device` is missing; `--no-overlay` shows the raw picture (only an `AI faces: N` counter) |
| `check_connection.py` | Checks the SSH/SFTP link step by step (address, Wi-Fi clash, port 22, login, AI results, firmware) and prints the fix for each failure | `--ip`, `--user`, `--password`; exit code `1` if a step failed |
| `example_IR.py` | Near-infrared live view with five processing modes | no SSH; `--device`, `--width/--height`, `--mode`, `--threshold`, `--flicker-filter`, `--frames`, `--no-display` |
| `example_audio.py` | Records the camera microphone (10 s by default) and saves a multi-channel `.wav` plus a per-channel power-spectrum `.png`; prints RMS, peak and strongest frequency per channel (§11) | `--duration`, `--device`, `--samplerate`, `--channels`, `--output-dir`, `--list`; no SSH |

Every script stops cleanly on **Ctrl+C** (a second press forces an exit), releases the
camera in a `finally` block and closes all windows. Exit codes: `0` normal, `2` camera
(or, for `example_audio.py`, microphone) not found / not openable, `3` (`example_IR.py`)
the camera stopped delivering frames, `4` (`example_audio.py`) the audio stream failed,
`1` error in `rgb_ai_capture.py` / `rgb_ai_live.py` (camera or connection), `130` interrupted with
Ctrl+C (`rgb_ai_capture.py`, `rgb_ai_live.py`, `example_audio.py`).

### Limits to keep in mind

* AI results only while the RGB stream is open **as MJPG**.
* Opening the IR stream next to an MJPG RGB stream roughly halves the frame rate of both,
  or starves the IR stream (§3). For 30 fps on both streams use RGB in NV12 or YUY2; the
  AI is then off.
* One face per result. The mesh is missing from some results (§7).
* Exaggerated head poses can lose the face.
* After a USB unplug the client does not reconnect by itself.
* Whether MJPG can be forced depends on the OS backend (§2).

---

## 11. Audio (USB microphone)

The camera has a microphone array. It shows up on your PC as an ordinary USB audio input
device, named `<product> Microphone` (`LVNext Microphone` by default). No network link,
login or configuration is needed: any program that can record from a microphone can use
it. This SDK adds a small recorder and a spectrum plot as a starting point.

### What the camera delivers

| Property | Value |
|---|---|
| USB class | USB Audio Class 1, capture only (no speaker output) |
| Sample format | signed 16-bit PCM, little endian |
| Sample rate | 48 kHz (16 kHz is also offered) |
| **Channels with audio** | **2** (channels 1 and 2) |
| Processing | none: raw microphone samples, with no noise suppression, echo cancellation, automatic gain control or filtering |
| Level | a fixed gain is applied on the camera; your OS may also show an input-volume slider that changes the level |

The camera captures more microphones than it sends over USB: only two channels carry
audio. The USB description also lists 4- and 6-channel formats, and a PC driver may offer
one of those. On Windows the microphone appears once per host API: `WASAPI` shows 2
channels, while `MME`, `DirectSound` and `WDM-KS` show 6. In the 6-channel entries
**channels 1 and 2 carry audio and channels 3–6 are digital silence.**
`example_audio.py` picks the entry with the most channels, records them all and flags
channels that are all zero or identical to another one; pass `--channels 2` to record only
the two real channels (or `--device <index>` to pick the WASAPI entry).

### Quick start

```
python example_audio.py              # 10 s from the camera microphone
python example_audio.py --list       # list the input devices (index, name, host API, channels)
python example_audio.py --duration 5 --device 3 --output-dir mycaptures
```

It saves `audio_<time>.wav` (one WAV channel per USB channel, 16-bit, lossless) and
`spectrum_<time>.png` (power spectral density of every channel, in dBFS/Hz from 0 Hz to
half the sample rate) into `audio_captures/`, and prints each channel's RMS level, peak
level and strongest frequency. Ctrl+C stops early and still saves what was recorded.

### Python API (`audio_utils`)

The samples are never mixed, resampled or filtered.

| Function / class | Purpose |
|---|---|
| `list_audio_devices()` | input devices: `index`, `name`, `hostapi`, `max_input_channels`, `default_samplerate` |
| `find_audio_device(device=None, min_channels=1)` | the camera microphone (by name, and by USB id on Linux); `device` = index or name part; raises `AudioDeviceNotFoundError` listing what exists |
| `record_audio(duration_s=10.0, device=None, samplerate=None, channels=None, stop_event=None)` | blocking; returns `(audio, samplerate, stats)`, `audio` is an `int16` array of shape `(samples, channels)`; `stats` has `xruns`, `duration_actual_s`, `channels`, `interrupted`… |
| `AudioRingRecorder(device_info, samplerate=None, channels=None, seconds=10)` | non-blocking recorder that always keeps the latest `seconds`; `start()`, `snapshot()`, `stats()`, `stop()` |
| `compute_power_spectrum(audio, samplerate, nperseg=1024)` | `(freqs_hz, psd_db)`, shapes `(F,)` and `(F, channels)`, Welch method, dBFS/Hz |
| `channel_stats(audio, samplerate)` | per channel: RMS and peak in dBFS, strongest frequency, `silent`, `duplicate_of` |
| `save_power_spectrum_plot(freqs_hz, psd_db, out_path, title=...)` | PNG, no window needed |
| `save_wav(path, audio, samplerate)` | multi-channel 16-bit WAV |

```python
from audio_utils import compute_power_spectrum, record_audio

audio, fs, stats = record_audio(duration_s=5)      # audio.shape == (5 * fs, channels)
freqs, psd_db = compute_power_spectrum(audio, fs)
```

dBFS here is relative to an amplitude of 1.0, so a full-scale sine reads -3 dB RMS and
0 dB peak.

### Troubleshooting audio

| Symptom | Action |
|---|---|
| `no camera microphone found` | plug the camera in; run `python example_audio.py --list` and pass `--device <index>` |
| 6 channels but 4 are silent, or only 2 channels, on Windows | the list shows the same microphone once per host API (WASAPI 2 channels, MME / DirectSound / WDM-KS 6 channels); channels 3–6 are silent in every case; use `--channels 2` or the WASAPI entry |
| All channels are silent or every sample is zero | Windows: Settings → Privacy & security → Microphone → allow desktop apps, and check the input is enabled and not muted; macOS: System Settings → Privacy & Security → Microphone → allow your terminal or editor, then restart it |
| `PortAudio library not found` | Linux: `sudo apt install libportaudio2` |
| Linux: the device is busy | PulseAudio or PipeWire may hold it; pick its entry in `--list`, or stop the other program |
| `xruns` above 0 | close other USB-heavy programs, use a USB 3 port without a hub |

---

## 12. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `Failed to connect to 192.168.1.10:22` | the PC's USB-Ethernet adapter has no `192.168.1.x` address, or the cable is out | set `192.168.1.20/24` (README §3); `ping 192.168.1.10` |
| Connects, but traffic goes elsewhere | your Wi-Fi also uses `192.168.1.0/24` | disconnect Wi-Fi for the test, or change the router's subnet; the camera's address is fixed |
| `Authentication failed` | wrong login | use the user name and password on your kit card; `LOGIWEBCAM_USER`, `LOGIWEBCAM_PASSWORD` |
| `ValueError: SSH user name and password … required` | not supplied | export `LOGIWEBCAM_USER` and `LOGIWEBCAM_PASSWORD`, then run `python check_connection.py` |
| `get_latest_ai_data()` returns `None` | no RGB MJPG reader running, or AI not started | open the RGB stream as MJPG and keep reading; run `cam.diagnose()` |
| `timestamp_ms` frozen | stream is YUY2/NV12, or nobody reads the RGB stream | check `cap.get(cv2.CAP_PROP_FOURCC)`; size before FOURCC; on macOS/Windows try another backend |
| `plugin_loaded: false` | the stream closed, or an unsupported format | (re)open the RGB MJPG stream |
| Overlays offset | the frame was resized before drawing | scale the coordinates by the same factor (§4) |
| Wrong camera opens | built-in webcam is index 0 | `--device <n>`; on Linux check `v4l2-ctl --list-devices` |
| IR example: colour or landscape picture | wrong camera | choose another `--device` |
| IR picture flickers | lit/unlit frames alternate | `--flicker-filter` |
| IR example: no camera found | cable, permissions, camera busy | see the `camera_hint()` message |
| `errno=28` in the YUV status | storage full | turn the snapshot off; use 640×480 |
| macOS: no frames / black | Camera permission missing for the terminal | System Settings → Privacy & Security → Camera |
| Linux: cannot open `/dev/video*` | not in the `video` group | `sudo usermod -aG video $USER`, log out and in |
| `PortAudio library not found` (Linux) | the system library is missing | `sudo apt install libportaudio2` |
| `example_audio.py`: no microphone found, or only silence | OS microphone permission, wrong input chosen, camera not listed as an audio device | see §11 *Troubleshooting audio*; `python example_audio.py --list` |
| `ImportError: libGL…` (Linux) or a window cannot open | headless OpenCV build installed | `pip uninstall opencv-python-headless; pip install opencv-python` |
