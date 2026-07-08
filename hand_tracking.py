# ============================================================
# hand_tracking.py
# AeroControl – AI Powered Touchless Gesture Control System
# Handles real-time hand detection and landmark extraction
# using Google MediaPipe Hands.
# ============================================================

import cv2
import mediapipe as mp


class HandTracker:
    """
    Wraps MediaPipe Hands to detect and draw hand landmarks
    from a webcam frame.  All downstream gesture logic reads
    the landmark list produced here.
    """

    # MediaPipe landmark indices for key fingertips & joints
    WRIST       = 0
    THUMB_TIP   = 4
    INDEX_TIP   = 8
    INDEX_MCP   = 5      # index finger knuckle (base)
    MIDDLE_TIP  = 12
    RING_TIP    = 16
    PINKY_TIP   = 20

    def __init__(
        self,
        max_hands: int = 1,
        detection_confidence: float = 0.75,
        tracking_confidence: float = 0.75,
    ):
        """
        Parameters
        ----------
        max_hands            : maximum number of hands to detect
        detection_confidence : minimum confidence for initial detection
        tracking_confidence  : minimum confidence to keep tracking
        """
        self.mp_hands    = mp.solutions.hands
        self.mp_draw     = mp.solutions.drawing_utils
        self.mp_styles   = mp.solutions.drawing_styles

        # Initialise MediaPipe Hands solution
        self.hands = self.mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            max_num_hands=1
        )

        # Cache last known landmarks so callers always get a value
        self._landmarks  = []
        self._hand_label = "Unknown"

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def find_hands(self, frame: "np.ndarray", draw: bool = True) -> "np.ndarray":
        """
        Run MediaPipe on *frame* (BGR) and optionally draw the
        landmark skeleton onto the frame.

        Returns the annotated frame.
        """
        # MediaPipe expects RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False          # small performance win
        self._results = self.hands.process(rgb)
        rgb.flags.writeable = True

        if draw and self._results.multi_hand_landmarks:
            for hand_lms in self._results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    frame,
                    hand_lms,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_styles.get_default_hand_landmarks_style(),
                    self.mp_styles.get_default_hand_connections_style(),
                )

        return frame

    def get_landmarks(self, frame: "np.ndarray", hand_index: int = 0) -> list:
        """
        Return a list of (id, x_pixel, y_pixel) tuples for every
        landmark of the requested hand.  Returns [] if no hand found.
        """
        self._landmarks = []
        h, w, _ = frame.shape

        if self._results.multi_hand_landmarks:
            if hand_index < len(self._results.multi_hand_landmarks):
                hand_lms = self._results.multi_hand_landmarks[hand_index]

                for lm_id, lm in enumerate(hand_lms.landmark):
                    # Convert normalised [0,1] coords → pixel coords
                    px, py = int(lm.x * w), int(lm.y * h)
                    self._landmarks.append((lm_id, px, py))

                # Store handedness label (Left / Right)
                if self._results.multi_handedness:
                    label = (
                        self._results.multi_handedness[hand_index]
                        .classification[0]
                        .label
                    )
                    self._hand_label = label

        return self._landmarks

    def get_finger_tip(self, tip_id: int) -> tuple | None:
        """
        Convenience: return (x, y) pixel position for a single
        landmark id, or None if landmarks are not available.
        """
        for lm_id, x, y in self._landmarks:
            if lm_id == tip_id:
                return (x, y)
        return None

    @property
    def hand_label(self) -> str:
        """'Left' or 'Right' for the currently tracked hand."""
        return self._hand_label

    def close(self):
        """Release MediaPipe resources."""
        self.hands.close()
