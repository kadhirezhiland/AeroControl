# ============================================================
# main.py
# AeroControl – AI Powered Touchless Gesture Control System
#
# Entry point:  python main.py
#
# Press  Q  or  ESC  to quit.
# Move the mouse to the TOP-LEFT screen corner to trigger the
# PyAutoGUI failsafe and force-quit if needed.
# ============================================================

import sys
import cv2
import pyautogui

from hand_tracking     import HandTracker
from gesture_controller import GestureController
from screenshot        import ScreenshotManager
from utils             import FPSCounter, draw_hud_panel, draw_text, CYAN


# ── Configuration ─────────────────────────────────────────────────
CAM_INDEX      = 0          # webcam index (try 1 if 0 doesn't work)
CAM_WIDTH      = 640        # capture width  (px)
CAM_HEIGHT     = 480        # capture height (px)
FLIP_FRAME     = True       # mirror webcam (natural for self-facing cam)
SMOOTH_ALPHA   = 0.18       # cursor smoothing  (0.05 slow … 0.5 fast)
WINDOW_NAME    = "AeroControl – Touchless Gesture System"
# ──────────────────────────────────────────────────────────────────


def main():
    # ── Screen resolution ─────────────────────────────────────────
    screen_w, screen_h = pyautogui.size()
    print(f"[AeroControl] Screen resolution: {screen_w} × {screen_h}")

    # ── Webcam setup ──────────────────────────────────────────────
    cap = cv2.VideoCapture(CAM_INDEX)

    if not cap.isOpened():
        print(f"[ERROR] Cannot open webcam at index {CAM_INDEX}.")
        print("        Try changing CAM_INDEX in main.py (e.g. CAM_INDEX = 1).")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 60)      # request 60 fps (honoured if hardware allows)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimise latency

    # ── Module initialisation ─────────────────────────────────────
    tracker    = HandTracker(
        max_hands=1,
        detection_confidence=0.75,
        tracking_confidence=0.75,
    )
    controller = GestureController(
        screen_width=screen_w,
        screen_height=screen_h,
        cam_width=CAM_WIDTH,
        cam_height=CAM_HEIGHT,
        smooth_alpha=SMOOTH_ALPHA,
    )
    fps_counter = FPSCounter(smoothing=20)

    print("[AeroControl] System online.  Press Q or ESC to quit.")

    # ── Main loop ─────────────────────────────────────────────────
    while True:
        # 1. Grab a frame from the webcam
        success, frame = cap.read()
        if not success:
            print("[WARNING] Failed to read frame from webcam. Retrying…")
            continue

        # 2. Mirror the frame (so it acts like a mirror, not a window)
        if FLIP_FRAME:
            # frame = cv2.flip(frame, 1)

        # 3. Detect hand landmarks (drawn in-place on frame)
        frame = tracker.find_hands(frame, draw=True)
        landmarks = tracker.get_landmarks(frame)

        # 4. Run gesture classification & execute system actions
        gesture_name = controller.update(landmarks, frame)

        # 5. Draw screenshot flash if active
        controller.screenshot.draw_flash(frame)

        # 6. Calculate and draw the HUD overlay
        fps = fps_counter.tick()
        draw_hud_panel(frame, fps, gesture_name)

        # 7. Show the annotated frame
        cv2.imshow(WINDOW_NAME, frame)

        # 8. Keyboard exit  (Q or ESC)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):   # 27 = ESC
            break

    # ── Cleanup ───────────────────────────────────────────────────
    print("[AeroControl] Shutting down…")
    tracker.close()
    cap.release()
    cv2.destroyAllWindows()
    print("[AeroControl] Goodbye!")


if __name__ == "__main__":
    main()