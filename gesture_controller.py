# ============================================================
# gesture_controller.py
# AeroControl – AI Powered Touchless Gesture Control System
#
# Interprets hand landmarks → high-level gestures and
# dispatches the corresponding OS actions (mouse, scroll,
# volume, screenshot).
#
# Gesture map
# -----------
# INDEX only up      → Virtual mouse (move cursor)
# INDEX + THUMB near → Left click (pinch)
# INDEX + MIDDLE up  → Scroll (two-finger scroll)
# THUMB + INDEX far  → Volume control
# ALL fingers closed → Screenshot (fist)
# ============================================================

import time
import pyautogui
import cv2

from hand_tracking import HandTracker
from volume_control import VolumeController
from screenshot    import ScreenshotManager
from utils         import distance, lerp, clamp, map_range, draw_text, CYAN, GREEN, YELLOW, RED


# ------------------------------------------------------------------
# Safety: disable PyAutoGUI fail-safe corner trigger while running
# (re-enable if you want the emergency mouse-to-corner kill switch)
# ------------------------------------------------------------------
pyautogui.FAILSAFE    = True   # move mouse to top-left corner to quit
pyautogui.PAUSE       = 0.0   # remove the default 0.1 s delay


# ------------------------------------------------------------------
# Finger-up detection helper
# ------------------------------------------------------------------

# Landmark IDs for each fingertip and its lower joint (PIP / MCP)
_FINGER_TIPS = {
    "thumb":  (4,  3),
    "index":  (8,  6),
    "middle": (12, 10),
    "ring":   (16, 14),
    "pinky":  (20, 18),
}


def _fingers_up(landmarks: list) -> dict[str, bool]:
    """
    Return a dict stating whether each finger is 'up' (extended).

    For fingers 2-5 the fingertip must be above (lower y pixel value)
    its proximal-intermediate joint.  The thumb is checked on x-axis
    because it extends sideways.

    Parameters
    ----------
    landmarks : list of (id, x, y) tuples from HandTracker

    Returns
    -------
    dict  e.g. {'thumb': True, 'index': True, 'middle': False, ...}
    """
    lm = {lid: (x, y) for lid, x, y in landmarks}
    up = {}

    for name, (tip_id, ref_id) in _FINGER_TIPS.items():
        if tip_id not in lm or ref_id not in lm:
            up[name] = False
            continue

        tip_x, tip_y = lm[tip_id]
        ref_x, ref_y = lm[ref_id]

        if name == "thumb":
            # Thumb extends horizontally; compare x coords
            # Works for right hand; flip for left hand if needed
            up["thumb"] = tip_x < ref_x  # right hand: tip moves left when open
        else:
            # Other fingers: tip y must be above ref y (smaller pixel y = higher)
            up[name] = tip_y < ref_y

    return up


# ------------------------------------------------------------------
# GestureController
# ------------------------------------------------------------------
BLUE = (255,0,0)
class GestureController:
    """
    Central controller: reads landmarks from HandTracker, classifies
    the current gesture, and triggers the appropriate system action.
    """

    # Gesture names (used in the HUD display)
    GESTURE_IDLE       = "Idle"
    GESTURE_MOUSE      = "Virtual Mouse"
    GESTURE_CLICK      = "Left Click"
    GESTURE_SCROLL     = "Scroll"
    GESTURE_VOLUME     = "Volume Control"
    GESTURE_SCREENSHOT = "Screenshot"

    def __init__(
        self,
        screen_width:  int,
        screen_height: int,
        cam_width:     int  = 640,
        cam_height:    int  = 480,
        smooth_alpha:  float = 0.4,
    ):
        """
        Parameters
        ----------
        screen_width / height  : OS display resolution
        cam_width  / height    : webcam frame dimensions
        smooth_alpha           : lerp factor for cursor smoothing
                                 (0.05 = very smooth, 0.5 = snappy)
        """
        self.screen_w = screen_width
        self.screen_h = screen_height
        self.cam_w    = cam_width
        self.cam_h    = cam_height
        self.alpha    = smooth_alpha

        # Smoothed cursor position (float accumulator)
        self._cur_x = screen_width  / 2.0
        self._cur_y = screen_height / 2.0

        # Click state (prevent repeated clicks while pinch is held)
        self._click_held      = False
        self._click_cooldown  = 0.0          # epoch

        # Scroll state
        self._prev_scroll_y: int | None = None

        # Sub-modules
        self.vol_ctrl    = VolumeController()
        self.screenshot  = ScreenshotManager(cooldown=2.5)

        # Active gesture label (updated every frame)
        self.gesture = self.GESTURE_IDLE

        # Margins (px): shrink the usable camera region for mapping
        # so the cursor reaches screen edges more easily
        self._margin_x = int(cam_width  * 0.12)
        self._margin_y = int(cam_height * 0.12)

    # ------------------------------------------------------------------
    # Main update  (call once per frame)
    # ------------------------------------------------------------------

    def update(self, landmarks: list, frame) -> str:
        """
        Classify the current gesture and execute the action.

        Parameters
        ----------
        landmarks : list of (id, x, y) from HandTracker.get_landmarks()
        frame     : the current BGR webcam frame (for debug drawing)

        Returns
        -------
        str  current gesture name
        """
        if not landmarks:
            self.gesture = self.GESTURE_IDLE
            return self.gesture

        lm = {lid: (x, y) for lid, x, y in landmarks}
        up = _fingers_up(landmarks)

        # ── Retrieve key landmark positions ──────────────────────────
        index_tip   = lm.get(8)
        thumb_tip   = lm.get(4)
        middle_tip  = lm.get(12)

        # ──────────────────────────────────────────────────────────────
        # GESTURE 1 ─ Screenshot  (fist: all fingers down)
        # ──────────────────────────────────────────────────────────────
        if not any(up.values()):
            self.gesture = self.GESTURE_SCREENSHOT
            if not self.screenshot.is_on_cooldown:
                self.screenshot.try_capture()
                self._draw_gesture_label(frame, self.gesture, RED)
            return self.gesture

        # ──────────────────────────────────────────────────────────────
        # GESTURE 2 ─ Volume Control  (thumb + index only, spread)
        # ──────────────────────────────────────────────────────────────
        if (
            up["thumb"]
            and up["index"]
            and not up["middle"]
            and not up["ring"]
            and not up["pinky"]
            and thumb_tip and index_tip
        ):
            self.gesture = self.GESTURE_VOLUME
            dist = distance(thumb_tip, index_tip)

            # Map distance [30 px – 220 px] → volume [0 – 100]
            vol = VolumeController.finger_distance_to_volume(dist, 30, 220)
            self.vol_ctrl.set_volume(vol)

            # Visual: line + circle between fingertips
            cv2.line(frame, thumb_tip, index_tip, YELLOW, 2)
            mid = ((thumb_tip[0]+index_tip[0])//2,
                   (thumb_tip[1]+index_tip[1])//2)
            cv2.circle(frame, mid, 8, YELLOW, -1)
            draw_text(frame, f"Vol {vol:.0f}%", (mid[0]+10, mid[1]),
                      color=YELLOW, font_scale=0.55)
            self._draw_gesture_label(frame, self.gesture, YELLOW)
            return self.gesture

        # ──────────────────────────────────────────────────────────────
        # GESTURE 3 - Scroll  (index + middle up, thumb/ring/pinky down)
        # ──────────────────────────────────────────────────────────────
        if (
            up["index"]
            and up["middle"]
            and not up["thumb"]
            and not up["ring"]
            and not up["pinky"]
            and index_tip
            and middle_tip
        ):
            self.gesture = self.GESTURE_SCROLL

            # Average Y of index and middle fingertips for stable control
            cur_y = (index_tip[1] + middle_tip[1]) // 2

            if self._prev_scroll_y is None:
                self._prev_scroll_y = cur_y
                self._scroll_accum = 0
                self._draw_gesture_label(frame, self.gesture, GREEN)
                return self.gesture

            delta = self._prev_scroll_y - cur_y

            # Dead zone: ignore tiny shaking
            if abs(delta) < 4:
                delta = 0

            # Accumulate movement for precision
            self._scroll_accum += delta

            # Scroll only when enough movement is collected
            SCROLL_STEP = 18      # lower = more sensitive, higher = more stable
            SCROLL_SPEED = 4      # lower = slow, higher = fast

            if abs(self._scroll_accum) >= SCROLL_STEP:
                scroll_units = int(self._scroll_accum / SCROLL_STEP)

                # limit sudden jump
                scroll_units = max(-3, min(3, scroll_units))

                pyautogui.scroll(scroll_units * SCROLL_SPEED)

                # keep remaining movement
                self._scroll_accum = self._scroll_accum % SCROLL_STEP

            # update previous slowly for smoothness
            self._prev_scroll_y = int(self._prev_scroll_y * 0.7 + cur_y * 0.3)

            cv2.line(frame, index_tip, middle_tip, GREEN, 2)
            self._draw_gesture_label(frame, self.gesture, GREEN)
            return self.gesture

        else:
            self._prev_scroll_y = None
            self._scroll_accum = 0
        # ──────────────────────────────────────────────────────────────
        # GESTURE 4 ─ Left Click  (pinch: index tip close to thumb tip)
        # ──────────────────────────────────────────────────────────────
        if up["index"] and thumb_tip and index_tip:
            pinch_dist = distance(index_tip, thumb_tip)

            if pinch_dist < 38:          # threshold in pixels
                if not self._click_held and time.time() > self._click_cooldown:
                    pyautogui.click()
                    self._click_held     = True
                    self._click_cooldown = time.time() + 0.4   # 400 ms debounce
                self.gesture = self.GESTURE_CLICK

                # Visual: circle at midpoint of pinch
                mid = ((index_tip[0]+thumb_tip[0])//2,
                       (index_tip[1]+thumb_tip[1])//2)
                cv2.circle(frame, mid, 14, RED, -1)
                cv2.circle(frame, mid, 14, (255,255,255), 1)
                self._draw_gesture_label(frame, self.gesture, RED)
                return self.gesture
            else:
                self._click_held = False   # release
        # ──────────────────────────────────────────────────────────────
        # GESTURE ─ Right Click
        # ──────────────────────────────────────────────────────────────
        if up["middle"] and thumb_tip and middle_tip:

            pinch_dist = distance(middle_tip, thumb_tip)

            if pinch_dist < 38:

                pyautogui.rightClick()

                self.gesture = "Right Click"

                mid = (
                    (middle_tip[0] + thumb_tip[0]) // 2,
                    (middle_tip[1] + thumb_tip[1]) // 2
                )

                cv2.circle(frame, mid, 14, RED, -1)

                self._draw_gesture_label(frame, self.gesture, RED)

                return self.gesture

        # ──────────────────────────────────────────────────────────────
        # GESTURE 5 ─ Virtual Mouse  (index finger up, others down)
        # ──────────────────────────────────────────────────────────────
        if up["index"] and index_tip:
            self.gesture = self.GESTURE_MOUSE
            self._move_cursor(index_tip[0], index_tip[1])

            # Visual cursor dot on camera feed
            cv2.circle(frame, index_tip, 10, CYAN, -1)
            cv2.circle(frame, index_tip, 10, (255,255,255), 1)
            self._draw_gesture_label(frame, self.gesture, CYAN)
            return self.gesture

        # ──────────────────────────────────────────────────────────────
        # Default
        # ──────────────────────────────────────────────────────────────
        self.gesture = self.GESTURE_IDLE
        return self.gesture

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _move_cursor(self, cam_x: int, cam_y: int):
        """
        Map a camera pixel coordinate to a screen coordinate and
        move the cursor with lerp smoothing.
        """
        # 1. Normalise within the active camera region (exclude margins)
        usable_x1 = self._margin_x
        usable_x2 = self.cam_w - self._margin_x
        usable_y1 = self._margin_y
        usable_y2 = self.cam_h - self._margin_y

        # 2. Map to screen coordinates
        target_x = map_range(cam_x, usable_x1, usable_x2, self.screen_w, 0)
        target_y = map_range(cam_y, usable_y1, usable_y2, 0, self.screen_h)

        # 3. Clamp to screen boundaries
        target_x = clamp(target_x, 0, self.screen_w - 1)      
        target_y = clamp(target_y, 0, self.screen_h - 1)

        # 4. Smooth via lerp
        self._cur_x = lerp(self._cur_x, target_x, self.alpha)
        self._cur_y = lerp(self._cur_y, target_y, self.alpha)

        # 5. Move (duration=0 = instant; smoothing handled by lerp above)
        pyautogui.moveTo(int(self._cur_x), int(self._cur_y))
    def _draw_gesture_label(self, frame, label: str, color: tuple):
        """Draw a small coloured dot next to the active gesture name."""
        h, w = frame.shape[:2]
        cv2.circle(frame, (w - 170, 30), 7, color, -1)