# ✋ AeroControl – AI Powered Touchless Gesture Control System

> Control your laptop with nothing but your hand — no touch, no hardware, just computer vision.

Built with **OpenCV**, **MediaPipe Hands**, and **PyAutoGUI**.

---

## 📁 Project Structure

```
AeroControl/
│
├── main.py               ← Entry point (run this)
├── hand_tracking.py      ← MediaPipe wrapper & landmark extraction
├── gesture_controller.py ← Gesture classification & OS actions
├── volume_control.py     ← Cross-platform volume control
├── screenshot.py         ← Screenshot capture + shutter flash
├── utils.py              ← Maths helpers, drawing, FPS counter
│
├── requirements.txt      ← Python dependencies
│
└── assets/
    └── screenshots/      ← Auto-created; gesture screenshots saved here
```

---

## ⚙️ Installation

### 1 — Prerequisites

| Requirement | Version |
|-------------|---------|
| Python      | 3.9 – 3.11 |
| pip         | latest  |
| Webcam      | any USB or built-in |

### 2 — Clone / Download the project

```bash
git clone https://github.com/your-username/AeroControl.git
cd AeroControl
```

### 3 — Create a virtual environment (recommended)

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 4 — Install dependencies

```bash
pip install -r requirements.txt
```

#### Windows extra (for volume control)

```bash
pip install pycaw comtypes
```

Then uncomment the two lines at the bottom of `requirements.txt`.

#### Linux extra (for volume control)

Ensure ALSA utils are installed:

```bash
sudo apt install alsa-utils   # Debian / Ubuntu
```

---

## ▶️ How to Run

```bash
python main.py
```

Press **Q** or **ESC** to quit.  
Move the mouse to the **top-left corner** of your screen to trigger the PyAutoGUI emergency exit.

### Configuration options (inside `main.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `CAM_INDEX` | `0` | Webcam index. Try `1` if 0 fails |
| `CAM_WIDTH` | `640` | Capture width (px) |
| `CAM_HEIGHT` | `480` | Capture height (px) |
| `FLIP_FRAME` | `True` | Mirror the webcam feed |
| `SMOOTH_ALPHA` | `0.18` | Cursor smoothing (0.05 = slow, 0.5 = snappy) |

---

## 🤌 Gesture Mapping Table

| # | Gesture | Hand Shape | Action | Visual Cue |
|---|---------|-----------|--------|------------|
| 1 | **Virtual Mouse** | ☝️ Index finger up only | Moves the mouse cursor | Cyan dot on fingertip |
| 2 | **Left Click** | 🤏 Pinch index + thumb | Single left mouse click | Red dot at pinch point |
| 3 | **Scroll** | ✌️ Index + middle up | Scroll up / down | Green line between fingers |
| 4 | **Volume Control** | 👌 Thumb + index spread | System volume (spread = louder) | Yellow line + vol % label |
| 5 | **Screenshot** | ✊ Fist (all fingers closed) | Full-screen screenshot | White shutter flash |

### Tips for best results

* **Good lighting** — face a light source; avoid strong backlight.
* **Plain background** — a plain wall behind your hand improves detection.
* **Hand distance** — keep your hand 30 – 70 cm from the camera.
* **Scroll vs Mouse** — use two fingers (index + middle) for scroll; one finger (index only) for cursor.
* **Volume** — pinch thumb and index together then spread apart to raise volume; bring together to lower.
* **Screenshot** — make a full fist briefly; there is a 2.5 s cooldown between captures.

---

## 🖥️ HUD Overlay

```
┌──────────────────────────┐              ┌──────────────┐
│ AeroControl  v1.0        │              │ Virtual Mouse│
│ FPS:  28.4               │              └──────────────┘
│ AI Gesture System        │
└──────────────────────────┘

         [live webcam with hand skeleton]

┄ Index=Mouse  Pinch=Click  2-Finger=Scroll  Thumb+Index=Vol  Fist=Screenshot ┄
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| `Cannot open webcam` | Change `CAM_INDEX` to `1` or `2` in `main.py` |
| Low FPS | Reduce `CAM_WIDTH`/`CAM_HEIGHT` to `320×240` |
| Cursor jitter | Decrease `SMOOTH_ALPHA` (e.g. `0.08`) |
| Gestures not detected | Improve lighting; keep hand clearly in frame |
| Volume not changing (Linux) | Run `amixer` in terminal; install `alsa-utils` |
| Volume not changing (Windows) | `pip install pycaw comtypes` |
| Screenshot not saving | Check write permissions in `assets/screenshots/` |

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `opencv-python` | Webcam capture & frame drawing |
| `mediapipe` | Hand landmark detection (21 points) |
| `pyautogui` | Mouse control & screenshot |
| `Pillow` | Image saving (used by pyautogui) |
| `numpy` | Array maths (transitive dep) |
| `pycaw` *(Windows)* | Core Audio volume API |

---

## 📸 Screenshots

Screenshots are auto-saved to:

```
AeroControl/assets/screenshots/aerocontrol_YYYYMMDD_HHMMSS.png
```

---

## 📄 License

MIT — free to use, modify, and distribute.
```
```
