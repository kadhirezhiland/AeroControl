# ============================================================
# app.py
# AeroControl – Flask Dashboard Server
#
# Run:  python app.py
# Open: http://localhost:5000
#
# Architecture
# ────────────
# 1. A background thread (CameraThread) captures webcam frames,
#    runs HandTracker + GestureController, and writes results
#    into a shared AppState object (protected by a lock).
#
# 2. Three Flask routes:
#    GET /              → serves the dashboard HTML page
#    GET /video_feed    → MJPEG stream (multipart/x-mixed-replace)
#    GET /stats         → JSON snapshot of gesture + FPS data
#
# The frontend polls /stats every 150 ms and displays an
# <img src="/video_feed"> for the live annotated video.
# ============================================================

import threading
import time
import cv2
from flask import Flask, Response, jsonify, render_template

# ── Import AeroControl modules (all in the same directory) ────
from hand_tracking      import HandTracker
from gesture_controller import GestureController
from utils              import FPSCounter, draw_hud_panel
import pyautogui


# ──────────────────────────────────────────────────────────────
# Configuration  (tweak here, not scattered through the code)
# ──────────────────────────────────────────────────────────────
CAM_INDEX      = 0       # webcam index; try 1 if 0 doesn't work
CAM_WIDTH      = 424     # capture width in pixels
CAM_HEIGHT     = 240     # capture height in pixels
FLIP_FRAME     = True    # True = mirror view (natural for self-facing cam)
JPEG_QUALITY   = 80      # MJPEG encode quality 1-100 (lower = faster)
SMOOTH_ALPHA   = 0.18    # cursor lerp factor (0.05 slow … 0.5 snappy)
STREAM_FPS_CAP = 30      # max frames/sec pushed to the MJPEG stream


# ──────────────────────────────────────────────────────────────
# Shared application state (written by camera thread,
# read by Flask routes)
# ──────────────────────────────────────────────────────────────
class AppState:
    """
    Thread-safe container for the latest frame and gesture data.
    All writes happen inside a threading.Lock; reads are lock-free
    for speed (Python's GIL makes attribute reads safe enough for
    the stats endpoint).
    """
    def __init__(self):
        self._lock        = threading.Lock()
        self.frame_bytes  = b""          # latest JPEG-encoded frame
        self.gesture      = "Idle"       # current gesture name
        self.fps          = 0.0          # smoothed FPS
        self.hand_visible = False        # True when a hand is detected
        self.gesture_counts = {          # cumulative trigger counter
            "Virtual Mouse":  0,
            "Left Click":     0,
            "Scroll":         0,
            "Volume Control": 0,
            "Screenshot":     0,
        }

    def update_frame(self, jpeg_bytes: bytes):
        with self._lock:
            self.frame_bytes = jpeg_bytes

    def get_frame(self) -> bytes:
        with self._lock:
            return self.frame_bytes

    def update_stats(self, gesture: str, fps: float, hand_visible: bool):
        with self._lock:
            prev = self.gesture
            self.gesture      = gesture
            self.fps          = fps
            self.hand_visible = hand_visible
            # Increment counter when a non-idle gesture first fires
            if gesture != prev and gesture in self.gesture_counts:
                self.gesture_counts[gesture] += 1

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "gesture":        self.gesture,
                "fps":            round(self.fps, 1),
                "hand_visible":   self.hand_visible,
                "gesture_counts": dict(self.gesture_counts),
            }


# Singleton shared state
state = AppState()


# ──────────────────────────────────────────────────────────────
# Background camera thread
# ──────────────────────────────────────────────────────────────
class CameraThread(threading.Thread):
    """
    Runs as a daemon thread.
    Continuously:
      1. Grabs a frame from the webcam
      2. Runs hand tracking (MediaPipe)
      3. Runs gesture classification
      4. Draws the HUD overlay
      5. JPEG-encodes the frame and stores it in AppState
      6. Updates gesture / FPS stats in AppState
    """

    def __init__(self):
        super().__init__(daemon=True)   # dies when main thread exits
        self._stop_event  = threading.Event()
        screen_w, screen_h = pyautogui.size()

        # Sub-modules (same ones used by main.py)
        self.tracker    = HandTracker(
            max_hands=1,
            detection_confidence=0.75,
            tracking_confidence=0.75,
        )
        self.controller = GestureController(
            screen_width=screen_w,
            screen_height=screen_h,
            cam_width=CAM_WIDTH,
            cam_height=CAM_HEIGHT,
            smooth_alpha=0.35,
        )
        self.fps_counter = FPSCounter(smoothing=20)

        # JPEG encode parameters (passed to cv2.imencode)
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY,55]

        # Frame-rate limiter for the stream (not the detection loop)
        self._frame_interval = 1 / 20

    def run(self):
        cap = cv2.VideoCapture(CAM_INDEX)
        cap.set(3, 640)
        cap.set(4, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            print(f"[CameraThread] ERROR: Cannot open webcam {CAM_INDEX}.")
            return

        # Request resolution and low-latency buffering
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        print("[CameraThread] Camera online.")
        last_push = 0.0   # epoch of last frame pushed to state

        while not self._stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            
            # ── 1. Mirror ────────────────────────────────────
            if FLIP_FRAME:                  
                frame = frame
            # ── 2. Hand detection ─────────────────────────────
            frame = self.tracker.find_hands(frame, draw=True)
            landmarks = self.tracker.get_landmarks(frame)

            # ── 3. Gesture classification & OS actions ────────
            gesture = self.controller.update(landmarks, frame)

            # ── 4. Screenshot flash ───────────────────────────
            self.controller.screenshot.draw_flash(frame)

            # ── 5. HUD overlay ────────────────────────────────
            fps = self.fps_counter.tick()
            draw_hud_panel(frame, fps, gesture)
            
            # ── 6. Store stats ────────────────────────────────
            state.update_stats(
                gesture=gesture,
                fps=fps,
                hand_visible=bool(landmarks),
            )

            # ── 7. JPEG-encode & push frame (rate-limited) ────
            now = time.perf_counter()
            if now - last_push >= self._frame_interval:
                _, buf = cv2.imencode(".jpg", frame, self._encode_params)
                state.update_frame(buf.tobytes())
                last_push = now

        # Clean up
        self.tracker.close()
        cap.release()
        print("[CameraThread] Camera released.")

    def stop(self):
        self._stop_event.set()


# ──────────────────────────────────────────────────────────────
# Flask application
# ──────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder='frontend',
    static_folder='frontend'
)


# ── Route 1: Dashboard page ───────────────────────────────────
@app.route("/")
def index():
    """Serve the main dashboard HTML."""
    return render_template("index.html")


# ── Route 2: MJPEG video stream ───────────────────────────────
def _mjpeg_generator():
    """
    Generator that yields annotated JPEG frames wrapped in the
    multipart/x-mixed-replace MJPEG envelope.  The browser's
    <img> tag re-renders on each part automatically.
    """
    boundary = b"--frame\r\n"
    header   = b"Content-Type: image/jpeg\r\n\r\n"
    tail     = b"\r\n"

    while True:
        frame_bytes = state.get_frame()

        if frame_bytes:
            yield boundary + header + frame_bytes + tail

        # Yield at most STREAM_FPS_CAP frames per second
        time.sleep(1.0 / STREAM_FPS_CAP)


@app.route("/video_feed")
def video_feed():
    """Live annotated MJPEG stream."""
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


# ── Route 3: JSON stats (polled by the dashboard JS) ──────────
@app.route("/stats")
def stats():
    """
    Returns a JSON object:
    {
      "gesture":        "Virtual Mouse",
      "fps":            28.4,
      "hand_visible":   true,
      "gesture_counts": { "Virtual Mouse": 12, "Left Click": 3, ... }
    }
    """
    return jsonify(state.get_stats())


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start the background camera + gesture thread
    cam_thread = CameraThread()
    cam_thread.start()
    print("[AeroControl] Dashboard → http://localhost:5000")

    # Run Flask (use_reloader=False prevents the thread starting twice)
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)