# ============================================================
# utils.py
# AeroControl – AI Powered Touchless Gesture Control System
# Shared helper functions used across all modules.
# ============================================================

import math
import time
import cv2
import numpy as np


# ------------------------------------------------------------------
# Math helpers
# ------------------------------------------------------------------

def distance(p1: tuple, p2: tuple) -> float:
    """
    Euclidean distance between two (x, y) points.

    Parameters
    ----------
    p1, p2 : (x, y) tuples

    Returns
    -------
    float  pixel distance
    """
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def lerp(current: float, target: float, alpha: float) -> float:
    """
    Linear interpolation for smooth cursor movement.

    alpha = 1.0  → instant snap to target
    alpha = 0.1  → very smooth / slow follow
    """
    return current + alpha * (target - current)


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to the closed interval [lo, hi]."""
    return max(lo, min(hi, value))


# ------------------------------------------------------------------
# Coordinate mapping
# ------------------------------------------------------------------

def map_range(
    value: float,
    in_min: float,
    in_max: float,
    out_min: float,
    out_max: float,
) -> float:
    """
    Map *value* from one numeric range to another (Arduino-style map).

    Example
    -------
    map_range(50, 0, 100, 0, 1920)  →  960.0
    """
    if in_max == in_min:
        return out_min
    ratio = (value - in_min) / (in_max - in_min)
    return out_min + ratio * (out_max - out_min)


# ------------------------------------------------------------------
# Drawing helpers  (dark-futuristic UI overlay)
# ------------------------------------------------------------------

# Colour palette (BGR)
CYAN    = (255, 220, 0)
GREEN   = (0, 255, 120)
RED     = (0, 80, 255)
WHITE   = (230, 230, 230)
YELLOW  = (0, 220, 255)
DARK_BG = (10, 10, 20)

FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_text(
    frame,
    text: str,
    pos: tuple,
    font_scale: float = 0.6,
    color: tuple = WHITE,
    thickness: int = 1,
    with_shadow: bool = True,
):
    """
    Render anti-aliased text with an optional dark shadow for
    readability against any background.
    """
    x, y = pos
    if with_shadow:
        # Shadow: offset by 2 px, drawn in near-black
        cv2.putText(
            frame, text, (x + 2, y + 2),
            FONT, font_scale, (5, 5, 5),
            thickness + 1, cv2.LINE_AA,
        )
    cv2.putText(frame, text, (x, y), FONT, font_scale, color, thickness, cv2.LINE_AA)


def draw_rounded_rect(
    frame,
    top_left: tuple,
    bottom_right: tuple,
    color: tuple,
    radius: int = 12,
    thickness: int = 1,
    fill_alpha: float = 0.0,
):
    """
    Draw a rounded rectangle.  If *fill_alpha* > 0 the interior is
    filled with *color* at the given transparency level (0–1).
    """
    x1, y1 = top_left
    x2, y2 = bottom_right
    r = radius

    if fill_alpha > 0.0:
        # Semi-transparent fill via a blended overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1 + r, y1), (x2 - r, y2), color, -1)
        cv2.rectangle(overlay, (x1, y1 + r), (x2, y2 - r), color, -1)
        for cx, cy in [(x1+r, y1+r), (x2-r, y1+r), (x1+r, y2-r), (x2-r, y2-r)]:
            cv2.circle(overlay, (cx, cy), r, color, -1)
        cv2.addWeighted(overlay, fill_alpha, frame, 1 - fill_alpha, 0, frame)

    # Draw border
    thickness = max(1, thickness)
    cv2.line(frame, (x1+r, y1), (x2-r, y1), color, thickness)
    cv2.line(frame,  (x1+r, y2), (x2-r, y2), color, thickness)
    cv2.line(frame,  (x1, y1+r), (x1, y2-r), color, thickness)
    cv2.line(frame,  (x2, y1+r), (x2, y2-r), color, thickness)
    cv2.ellipse(frame, (x1+r, y1+r), (r,r), 180, 0, 90, color, thickness)
    cv2.ellipse(frame, (x2-r, y1+r), (r,r), 270, 0, 90, color, thickness)
    cv2.ellipse(frame, (x1+r, y2-r), (r,r),  90, 0, 90, color, thickness)
    cv2.ellipse(frame, (x2-r, y2-r), (r,r),   0, 0, 90, color, thickness)


def draw_hud_panel(frame, fps: float, gesture_name: str):
    """
    Render the dark HUD overlay:
      • top-left  → branding + FPS
      • top-right → active gesture label
      • bottom bar → gesture cheat-sheet
    """
    h, w = frame.shape[:2]

    # ── Top-left info card ──────────────────────────────────────
    draw_rounded_rect(
        frame, (8, 8), (260, 80),
        color=DARK_BG, radius=10, thickness=1, fill_alpha=0.55,
    )
    draw_text(frame, "AeroControl  v1.0", (18, 32), font_scale=0.65, color=CYAN)
    draw_text(frame, f"FPS: {fps:5.1f}", (18, 58), font_scale=0.55, color=GREEN)
    draw_text(frame, "AI Gesture System", (18, 74), font_scale=0.38, color=WHITE)

    # ── Active gesture badge (top-right) ────────────────────────
    label = f"  {gesture_name}  "
    (tw, th), _ = cv2.getTextSize(label, FONT, 0.65, 1)
    pad = 10
    rx2 = w - 8
    rx1 = rx2 - tw - 2 * pad
    draw_rounded_rect(
        frame, (rx1, 8), (rx2, 44),
        color=YELLOW, radius=8, thickness=1, fill_alpha=0.35,
    )
    draw_text(frame, label, (rx1 + pad, 32), font_scale=0.65, color=YELLOW)

    # ── Bottom cheat-sheet bar ───────────────────────────────────
    hints = [
        "Index=Mouse",
        "Pinch=Click",
        "2-Finger=Scroll",
        "Thumb+Index=Vol",
        "Fist=Screenshot",
    ]
    bar_h = 26
    draw_rounded_rect(
        frame, (0, h - bar_h - 4), (w, h - 2),
        color=DARK_BG, radius=0, thickness=0, fill_alpha=0.60,
    )
    spacing = w // len(hints)
    for i, hint in enumerate(hints):
        draw_text(
            frame, hint,
            (i * spacing + 6, h - 8),
            font_scale=0.38, color=CYAN, thickness=1,
        )


# ------------------------------------------------------------------
# FPS tracker
# ------------------------------------------------------------------

class FPSCounter:
    """Lightweight rolling-average FPS tracker."""

    def __init__(self, smoothing: int = 15):
        self._times: list[float] = []
        self._smoothing = smoothing

    def tick(self) -> float:
        """
        Call once per frame.  Returns the current smoothed FPS.
        """
        now = time.perf_counter()
        self._times.append(now)
        if len(self._times) > self._smoothing:
            self._times.pop(0)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0
