# LogiInsight Webcam - PC Python SDK

Python SDK and examples for the LogiInsight hackathon webcam.
Works on Windows, macOS and Linux with Python 3.9+.

From a normal PC you can:

* read the **RGB** video stream with OpenCV,
* read the **near-infrared (IR)** video stream,
* read the on-device **AI results** (face box + 478-point face mesh) and switch the models on and off over USB networking,
* record the camera's **microphone** and look at its power spectrum.

## Download

* [logiinsight_api_sdk_v1.5.0.zip](../res/logiinsight_api_sdk_v1.5.0.zip) - SDK, examples and README (MIT licensed)

## Quick start

Unzip, then from the `logiinsight_api` folder:

```
uv sync                       # creates .venv and installs the dependencies
uv run python example_IR.py   # live near-infrared view
```

You can use plain `pip install -r requirements.txt` in a virtual environment instead of `uv`. Video and microphone work as soon as the camera is plugged in. The AI results need a USB network address on your PC; the zip's `README.md` explains the setup, and the SSH login is the one printed on your hackathon kit.

## Documentation

* [API reference](./API.md) - architecture, video streams, `LogiWebcamClient`, `camera_utils`, AI output JSON, audio, troubleshooting

## Examples

| Script | What it does |
|---|---|
| `example.py` | Captures RGB frames with the face box and mesh drawn, saved as PNG + JSON |
| `example2.py` | The same overlays in a live window |
| `example_IR.py` | Live near-infrared view with several processing modes |
| `example_audio.py` | Records the camera microphone to a `.wav` and a power-spectrum `.png` |

## License

MIT, Copyright (c) 2026 Logitech Europe S.A. See the `LICENSE` file in the zip.
