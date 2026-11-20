# LogiInsight Webcam — PC Python SDK

**Version 1.5.1** · Windows, macOS and Linux · Python 3.9+

> **This SDK is for the LogiInsight webcam in your hackathon kit.** The AI-enabled examples
> (face box, face mesh, AI JSON over USB networking) only work with that camera, because
> the AI runs *inside* it. With any other webcam (Logitech MX Brio, your own webcam, a
> laptop's built-in camera) you can at most look at the video: the on-device AI results
> do not exist there. Use a desktop library such as MediaPipe for those cameras.

Python SDK and examples for the LogiInsight hackathon webcam. From a normal PC you can:

* read the **RGB** video stream with OpenCV,
* read the **near-infrared (IR)** video stream: a monochrome sensor that responds to a
  wide range of near-infrared wavelengths, lit by the camera's own illuminator,
* read the on-device **AI results** (face box and 478-point face mesh) and switch the
  models on and off over USB networking,
* record the camera's **microphone** (2 channels).

## Download

* [logiinsight_api_sdk_v1.5.1.zip](https://github.com/Logitech/hackathons/releases/download/logiinsight-sdk-v1.5.1/logiinsight_api_sdk_v1.5.1.zip) - SDK, examples and README (MIT licensed)

The full reference is **[API reference](./API.md)**. Using an AI assistant? See
[section 7](#7-using-an-ai-assistant-with-these-docs).

> **No Conda / Anaconda.** Use `uv` or plain `pip` + `venv`, as shown below.

---

## 1. Install

Unzip the download, then run the commands in the `logiinsight_api` folder. Pick one way.

**uv (recommended)** — [install uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv sync                      # creates .venv and installs the dependencies
uv run python example_IR.py  # run any script through uv
```

**pip + venv**

```bash
# Linux / macOS
python3 -m venv .venv && source .venv/bin/activate
# Windows
#   py -m venv .venv
#   .venv\Scripts\activate
pip install -r requirements.txt
```

Dependencies: `paramiko`, `numpy`, `opencv-python` (the normal build, **not**
`opencv-python-headless`, because the examples open windows), and for the microphone
`sounddevice`, `scipy` and `matplotlib`.

**Linux only:** the microphone needs the PortAudio system library, otherwise importing
`sounddevice` fails with `PortAudio library not found`:

```bash
sudo apt install libportaudio2
```

---

## 2. Plug in and check the video (no network setup needed)

Connect the camera with a USB 3 cable. Video works immediately. The camera shows up under
these names (they start with the product name, `LVNext` by default):

| Camera name | What it is | Used by this SDK |
|---|---|---|
| `… Camera` | RGB sensor: MJPG / YUY2 / NV12 | `rgb_ai_capture.py`, `rgb_ai_live.py` |
| `… CPD Camera` | near-infrared sensor, MJPG, **portrait** frames | `example_IR.py` |
| `… Hello Camera` | Windows Hello stream | not used: ignore it, camera apps cannot open it |

The camera is also a USB microphone, so camera apps such as PotPlayer or Zoom list
`LVNext Microphone` next to the cameras. That is expected (see the microphone section below).

```bash
uv run python example_IR.py          # live near-infrared view with contrast / threshold modes
```

* macOS: allow the camera for your terminal (System Settings → Privacy & Security → Camera).
* Windows: Settings → Privacy & security → Camera → allow desktop apps.
* Linux: your user must be in the `video` group.

If the wrong camera opens (for example a laptop's built-in webcam), pass
`--device <index>`; try 0, 1, 2 … until the picture is right.

### Microphone (no network setup either)

The camera is also a USB microphone (`LVNext Microphone` by default). It sends **2
channels** to the PC: raw 16-bit samples at 48 kHz, no noise suppression or other
processing. Record 10 seconds and save a `.wav` plus a power-spectrum `.png`:

```bash
uv run python example_audio.py             # files go to ./audio_captures/
uv run python example_audio.py --list      # which input devices exist
```

Allow microphone access for your terminal (macOS: System Settings → Privacy & Security →
Microphone; Windows: Settings → Privacy & security → Microphone). On Windows the same
microphone can be listed once per audio host API with different channel counts (`WASAPI`
shows 2, `MME` / `DirectSound` / `WDM-KS` show 6). Only channels 1 and 2 carry audio; add
`--channels 2` to record just those. More in [API reference](./API.md#11-audio-usb-microphone).

---

## 3. Connect to the camera for the AI data (SSH/SFTP), step by step

`rgb_ai_capture.py` and `rgb_ai_live.py` read the AI results over SSH/SFTP through a
virtual Ethernet adapter that the camera creates (USB NCM). The camera side is already set
up and has the fixed address **`192.168.1.10`**. On your PC you only do the following, once.
The **user name and password are on the card in your kit.**

**Step 1 — Plug in** the camera with the USB 3 cable and give it a minute to start.

**Step 2 — Find the new network adapter.**

| OS | How |
|---|---|
| Windows | Press **Ctrl + R**, type **`ncpa.cpl`**, press Enter. This opens *Network Connections*. A **new Ethernet adapter** appears when you plug in the camera (its name may contain *USB*, *NCM* or *LVNext*; it says *Unidentified network*). **No new adapter?** See "Windows does not show the adapter" below. |
| macOS | System Settings → Network. A new entry appears when you plug in (for example *LVNext* or *USB 10/100 LAN*). |
| Linux | `ip -br link` — look for the new adapter (`usb0` or `enx…`). |

**Step 3 — Give that adapter a fixed address:** IP **`192.168.1.20`**, subnet mask
**`255.255.255.0`**, and **leave router/gateway and DNS empty** (so your Wi-Fi internet keeps
working).

| OS | How |
|---|---|
| Windows | In *Network Connections* (`ncpa.cpl`): right-click the new adapter → *Properties* → *Internet Protocol Version 4 (TCP/IPv4)* → *Properties* → *Use the following IP address*: IP `192.168.1.20`, mask `255.255.255.0`, gateway and DNS **empty** → OK → OK. |
| macOS | Select the new entry → *Details…* → *TCP/IP* → *Configure IPv4:* **Manually**, IP `192.168.1.20`, mask `255.255.255.0`, router **empty** → OK. |
| Linux | `sudo ip addr add 192.168.1.20/24 dev <adapter>` and `sudo ip link set <adapter> up` |

**Step 4 — Test the link:** `ping 192.168.1.10` must answer. (Windows: if the *first* ping
times out and the others answer, that is fine.)

**Step 5 — Give the SDK your user name and password** (from the card). Do **not** write
them into code or files. Set them as environment variables in the terminal you will run Python in:

```bash
export LOGIWEBCAM_USER='<user name on your card>'            # Linux / macOS
export LOGIWEBCAM_PASSWORD='<password on your card>'
```
```bat
set LOGIWEBCAM_USER=<user name on your card>                 &:: Windows (cmd)
set LOGIWEBCAM_PASSWORD=<password on your card>
```

(`--user` and `--password` exist too, but then the password shows in your shell history.)

**Step 6 — Let the checker look at everything:**

```bash
uv run python check_connection.py
```

It tests each step above (address, Wi-Fi clash, port 22, login, AI results, firmware) and
prints `[PASS]`, `[WARN]` or `[FAIL]` with the exact fix for your OS. Fix the first `[FAIL]`
and run it again.

**Step 7 — Run an RGB example:**

```bash
uv run python rgb_ai_capture.py --face-mesh          # 10 annotated PNG+JSON pairs in ./captures
uv run python rgb_ai_capture.py --face-mesh --frames 30
uv run python rgb_ai_live.py --face-mesh             # live window with overlays (q / ESC quits)
```

### Optional: try the login manually

```bash
sftp <user name on your card>@192.168.1.10           # type the password when asked
sftp> ls /files/logi_conf                            # the AI files are here
sftp> bye
```

If your computer complains *REMOTE HOST IDENTIFICATION HAS CHANGED* because you used
another device at this address before, run `ssh-keygen -R 192.168.1.10` once and try again.
The Python SDK is not affected.

### Windows does not show the adapter

Press **Ctrl + R**, type **`devmgmt.msc`**. If a device called *CDC NCM* sits under
*Other devices*: right-click it → *Update driver* → *Browse my computer for drivers* →
*Let me pick from a list of available drivers on my computer* → *Network adapters* →
*Microsoft* → **UsbNcm Host Device**. Step-by-step with pictures:
[Device drivers for CDC-NCM devices](https://community.smarttech.com/Customer/s/article/Device-drivers-for-CDC-NCM-device?language=en_US).
Also try another USB 3 cable or port.

### It works on Ethernet but not with Wi-Fi on (macOS, sometimes Windows)

* **Wi-Fi uses `192.168.1.x` as well** (very common for home routers and some campus
  networks): the PC cannot tell which network `192.168.1.10` is on. Turn Wi-Fi off while you
  work with the camera, or join another Wi-Fi (a phone hotspot usually works), then run
  `check_connection.py` again.
* **macOS sends the traffic to Wi-Fi:** System Settings → Network → `…` menu → *Set Service
  Order* and drag the camera's adapter **above** Wi-Fi, or run
  `sudo route -n add -host 192.168.1.10 -interface <enX of the camera adapter>`.
* **macOS "Local Network" permission:** System Settings → Privacy & Security → *Local
  Network* → switch **on** your terminal (and VS Code, or whatever you start Python from).
  Without it, connections to `192.168.1.10` fail with *No route to host* or time out.
* A **VPN** or a strict firewall can also block it: disconnect the VPN, and allow Python on a
  *Private* network when Windows asks.

---

## 4. Scripts

| Script | Purpose | Needs SSH |
|---|---|---|
| `rgb_ai_capture.py` | RGB: capture frames + AI JSON, save annotated PNG/JSON pairs (`--device-snapshot` for exactly paired frames) | yes |
| `rgb_ai_live.py` | RGB: live window with face box / mesh overlays (`--no-overlay` shows the raw picture) | yes |
| `example_IR.py` | Near-infrared live view: `raw`, contrast `stretch`, `clahe`, `threshold`, `otsu` (keys: `m` mode, `+`/`-` threshold, `s` save, `q` quit) | no |
| `example_audio.py` | Microphone: record 10 s (`--duration`), save a multi-channel `.wav` and a per-channel power-spectrum `.png`, print RMS / peak / strongest frequency | no |
| `check_connection.py` | Step-by-step check of the SSH/SFTP link, with fixes | yes |
| `logiwebcam.py` | The client library (`LogiWebcamClient`) | — |
| `camera_utils.py` | Camera discovery / opening helpers used by the IR example | — |
| `audio_utils.py` | Microphone discovery, multi-channel capture, power spectrum, WAV / PNG export | — |

All scripts stop cleanly on **Ctrl+C** (the camera is released and windows are closed).

```bash
uv run python example_IR.py --mode clahe
uv run python example_IR.py --width 1024 --height 1280
```

---

## 5. Things worth knowing

* **AI results only exist while the RGB stream is open as MJPG.** On macOS (AVFoundation)
  and Windows (MSMF) OpenCV often ignores the MJPG request and you get raw video; the
  scripts warn when that happens. Set the size *before* the format (the examples do). If
  the AI results stop updating, the examples print a warning after 2 seconds.
* **Coordinates are stream pixels**: pixels of the video size you opened (for example
  1920×1080). You can draw them directly on the frame.
* **The camera draws nothing on the video.** Boxes and landmarks exist only in the JSON; you
  draw them yourself (the examples show how).
* **The IR picture is portrait and grey** (256×320, 512×640 or 1024×1280).
* **RGB and IR can run together, but not both at full rate with the AI.** With RGB as MJPG
  (needed for the AI) each stream typically runs at about 15 fps, or the IR stream at about
  1 fps. With RGB as NV12 or YUY2 both streams run at 30 fps, but the AI is off. Open the
  RGB stream first.
* At most one face is reported per result.

### Why the picture and the JSON can differ (synchronization)

You get the AI results by a different route than the video: the **video** comes over USB
(UVC), the **AI JSON** is a file the camera updates and that you read over SSH/SFTP. The AI
also runs a little *behind* the video (it analyses a frame while the next ones are already
streaming). So when you draw the latest JSON on the frame you just received, the box can
sit slightly behind a moving face. That is **expected**, not a bug. It is most visible with
fast motion.

If you need the box to match the picture **exactly**:

```bash
uv run python rgb_ai_capture.py --face-mesh --device-snapshot
```

This switches on the camera's snapshot mode (`enable_yuv_snapshot`). The camera then saves,
together with each JSON, **the very frame the AI analysed**; the SDK reads both and pairs
them by an 8-byte timestamp in the file header (`yuv_capture_timestamp_ms` in the JSON), so
image and JSON always belong together. The price: one snapshot takes about **2 seconds** at
1920×1080, and the picture is the frame the AI saw, which is not necessarily the frame
the live video showed at that moment — so the *live* image and the snapshot of the same
instant can look different. The camera's storage is small, so the examples switch the snapshot
mode off again when they finish.

### If you do not want the camera's built-in AI

Switch it off (the camera then runs no AI model; the JSON keeps updating, but its `faces`
list stays empty):

```python
from logiwebcam import LogiWebcamClient

with LogiWebcamClient() as cam:           # user name and password come from the environment
    cam.set_ai_config(enable_face_detection=False, enable_face_mesh=False)
```

The setting stays until a program changes it; the RGB examples switch face detection back
on when they start. Or simply open the RGB camera as **YUY2 or NV12** instead of MJPG: the AI
does not run on those formats (and RGB + IR then both run at 30 fps).

---

## 6. Troubleshooting

Run **`python check_connection.py`** first; it finds most problems below.

| Symptom | Fix |
|---|---|
| `No near-infrared (CPD) camera found` | Check the cable, close apps that use the camera, check the OS camera permission; try `--device 0`, `1`, `2` … |
| IR example shows a colour or landscape picture | Wrong camera: choose another `--device`. |
| `SSH user name and password … required` | Set `LOGIWEBCAM_USER` and `LOGIWEBCAM_PASSWORD` (section 3, step 5) in the same terminal. |
| `Authentication failed` | Compare with the card in your kit; copy the values exactly. In Windows `cmd` no quotes after `set`; in macOS/Linux use single quotes. |
| `Failed to connect to 192.168.1.10` | The adapter has no `192.168.1.x` address yet (section 3), Wi-Fi uses the same subnet, or macOS needs the Local Network permission (see above). |
| AI JSON never changes / `timestamp_ms` frozen | The RGB stream is not MJPG, or no program is reading the RGB stream. |
| `faces` is always empty | Face detection is switched off (`set_ai_config(enable_face_detection=False)`): switch it on again, or run `rgb_ai_capture.py` / `rgb_ai_live.py`, which do. |
| `Cannot open … camera` on Linux | `ls /dev/video*`; add your user to the `video` group, log out and in. |
| macOS: black window / no frames | Allow Camera access for the terminal app, then restart it. |
| `PortAudio library not found` (Linux) | `sudo apt install libportaudio2` |
| `example_audio.py`: no microphone found / silent channels | Allow Microphone access for the terminal app; run `--list` and choose the camera's entry with `--device`; on Windows the entries differ in channel count (see above). |

More in [API reference](./API.md#12-troubleshooting).

---

## 7. Using an AI assistant with these docs

You can let a coding assistant (ChatGPT, Claude, Copilot, …) help you. Give it the
documentation links instead of pasting files; most assistants can fetch them:

* Documentation site: <https://logitech.github.io/hackathons/>
* API reference (raw text, easy for an assistant to read):
  <https://raw.githubusercontent.com/Logitech/hackathons/master/docs/logiinsight/API.md>
* This page (raw text):
  <https://raw.githubusercontent.com/Logitech/hackathons/master/docs/logiinsight/index.md>

For example, start your chat with: *"Read these pages first, then help me write code for the
LogiInsight webcam: <links>. The camera's AI results come from an SSH/SFTP JSON file, the video
from OpenCV."*

**Never paste the user name or password from your kit card into a chat with an assistant** or
into a file you share. The code reads them from the `LOGIWEBCAM_USER` and
`LOGIWEBCAM_PASSWORD` environment variables, and your assistant's code should do the same.

## License

MIT, see the `LICENSE` file in the zip. Copyright (c) 2026 Logitech Europe S.A.
