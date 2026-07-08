# ============================================================
# screenshot.py
# AeroControl – AI Powered Touchless Gesture Control System
#
# Captures a full-screen screenshot, saves it with a
# timestamped filename and shows a brief on-screen flash.
# ============================================================

import time
import os
import cv2
import pyautogui


# ------------------------------------------------------------------
# Directory setup
# ------------------------------------------------------------------

# Screenshots saved inside  AeroControl/assets/screenshots/
_SAVE_DIR = os.path.join(os.path.dirname(__file__), "assets", "screenshots")
os.makedirs(_SAVE_DIR, exist_ok=True)


# ------------------------------------------------------------------
# Screenshot manager
# ------------------------------------------------------------------

class ScreenshotManager:
    """
    Takes screenshots on gesture trigger with a cooldown to
    prevent multiple captures from a single held gesture.

    Usage
    -----
    sm = ScreenshotManager(cooldown=2.0)
    if sm.try_capture():
        print("Screenshot saved!")
    """

    def __init__(self, cooldown: float = 2.5):
        """
        Parameters
        ----------
        cooldown : seconds to wait before another screenshot can
                   be triggered (prevents burst-capturing).
        """
        self._cooldown   = cooldown
        self._last_time  = 0.0          # epoch of last capture
        self._flash_until = 0.0         # epoch until which the flash overlay shows

        self.last_filename = ""         # path of most recent screenshot

    # ------------------------------------------------------------------

    def try_capture(self) -> bool:
        """
        Attempt to capture a screenshot.

        Returns True if a screenshot was actually taken,
        False if still within the cooldown window.
        """
        now = time.time()
        if now - self._last_time < self._cooldown:
            return False                # cooldown not elapsed

        # Build timestamped filename
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(_SAVE_DIR, f"aerocontrol_{ts}.png")

        # Capture with PyAutoGUI (returns a PIL Image)
        img = pyautogui.screenshot()
        img.save(filename)

        self._last_time   = now
        self._flash_until = now + 0.4   # 400 ms white flash
        self.last_filename = filename

        print(f"[Screenshot] Saved → {filename}")
        return True

    # ------------------------------------------------------------------

    def draw_flash(self, frame) -> None:
        """
        If we're within the post-capture flash window, render a
        brief white overlay on *frame* (in-place) to mimic a camera
        shutter effect.
        """
        if time.time() < self._flash_until:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]),
                          (255, 255, 255), -1)
            alpha = max(0.0, (self._flash_until - time.time()) / 0.4)
            cv2.addWeighted(overlay, alpha * 0.6, frame, 1 - alpha * 0.6, 0, frame)

    # ------------------------------------------------------------------

    @property
    def is_on_cooldown(self) -> bool:
        """True while another screenshot cannot be taken yet."""
        return (time.time() - self._last_time) < self._cooldown
