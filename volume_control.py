# ============================================================
# volume_control.py
# AeroControl – AI Powered Touchless Gesture Control System
#
# Cross-platform system volume control.
# • Linux   → uses 'amixer' (ALSA) via subprocess
# • macOS   → uses 'osascript' via subprocess
# • Windows → uses pycaw / comtypes
#
# Falls back gracefully if the platform API is unavailable.
# ============================================================

import platform
import subprocess
import math


# ------------------------------------------------------------------
# Internal helpers – one per platform
# ------------------------------------------------------------------

def _set_volume_linux(level: int):
    """
    Set ALSA master volume to *level* (0–100).
    Requires 'amixer' to be installed (standard on most distros).
    """
    subprocess.run(
        ["amixer", "-q", "sset", "Master", f"{level}%"],
        check=False,
    )


def _set_volume_macos(level: int):
    """
    Set macOS output volume to *level* (0–100) via AppleScript.
    """
    subprocess.run(
        ["osascript", "-e", f"set volume output volume {level}"],
        check=False,
    )


def _set_volume_windows(level: int):
    """
    Set Windows master volume using pycaw (Core Audio API).
    pycaw must be installed: pip install pycaw comtypes
    """
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # pycaw works in decibels; convert percentage to scalar [0,1]
        scalar = level / 100.0
        volume.SetMasterVolumeLevelScalar(scalar, None)

    except ImportError:
        # pycaw not installed – silently skip
        pass


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

class VolumeController:
    """
    Simple cross-platform master volume controller.

    Usage
    -----
    vc = VolumeController()
    vc.set_volume(60)   # sets 60 %
    vc.change_by(+5)    # increase by 5 %
    """

    def __init__(self):
        self._level = 50          # assumed starting volume (%)
        self._os = platform.system()   # 'Linux', 'Darwin', 'Windows'

    # ------ low-level dispatch ----------------------------------------

    def _apply(self):
        """Push the cached *_level* to the OS."""
        lvl = int(self._level)
        if self._os == "Linux":
            _set_volume_linux(lvl)
        elif self._os == "Darwin":
            _set_volume_macos(lvl)
        elif self._os == "Windows":
            _set_volume_windows(lvl)
        # else: unknown platform – no-op

    # ------ public methods --------------------------------------------

    def set_volume(self, level: float):
        """
        Set absolute volume.

        Parameters
        ----------
        level : float   desired volume in percent [0 – 100]
        """
        self._level = max(0.0, min(100.0, level))
        self._apply()

    def change_by(self, delta: float):
        """
        Increase or decrease volume by *delta* percent.

        Parameters
        ----------
        delta : float   positive → louder, negative → quieter
        """
        self.set_volume(self._level + delta)

    @property
    def level(self) -> float:
        """Current cached volume level (0–100)."""
        return self._level

    # ------ convenience: map finger distance → volume -----------------

    @staticmethod
    def finger_distance_to_volume(
        distance_px: float,
        min_dist: float = 20.0,
        max_dist: float = 200.0,
    ) -> float:
        """
        Map a pixel distance (e.g. thumb↔index spread) linearly
        to a volume percentage [0 – 100].

        Parameters
        ----------
        distance_px : measured pixel distance between fingertips
        min_dist    : distance that maps to 0 %
        max_dist    : distance that maps to 100 %

        Returns
        -------
        float  clamped volume [0, 100]
        """
        if max_dist == min_dist:
            return 0.0
        ratio = (distance_px - min_dist) / (max_dist - min_dist)
        return max(0.0, min(100.0, ratio * 100.0))
