"""
AirDraw first-launch onboarding, gesture guide, and camera error handling.

Provides an interactive pre-camera onboarding screen that explains all supported
gestures, shape tools, color swatches, erasing, translation, and keyboard shortcuts
before initializing the webcam and MediaPipe.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple
import cv2 as cv
import numpy as np


class AppState(Enum):
    """Lifecycle states for AirDraw."""
    ONBOARDING = "ONBOARDING"
    INITIALIZING_CAMERA = "INITIALIZING_CAMERA"
    DRAWING = "DRAWING"
    CAMERA_ERROR = "CAMERA_ERROR"
    EXITING = "EXITING"


@dataclass
class GestureCard:
    """Authoritative metadata specification for a supported gesture or control."""
    id: str
    tag: str
    title: str
    pose: str
    description: str
    note: str
    shortcut: Optional[str] = None
    diagram_key: str = ""


# Shared source of truth for gesture definitions
GESTURE_DEFINITIONS: List[GestureCard] = [
    GestureCard(
        id="hover",
        tag="NAVIGATE",
        title="Hover to Move Cursor",
        pose="1 Finger (Index extended)",
        description="Raise your index finger only. Point to move cursor across canvas and hover over toolbar buttons to select colors or tools.",
        note="Passive cursor navigation — no drawing occurs in Hover mode.",
        shortcut="Index finger up",
        diagram_key="hover",
    ),
    GestureCard(
        id="draw",
        tag="DRAW",
        title="Draw Strokes & Shapes",
        pose="2 Fingers (Index + Middle)",
        description="Raise index and middle fingers together. Move your hand to paint freehand strokes or define shape dimensions.",
        note="Active drawing mode. Curl your middle finger back to pause drawing.",
        shortcut="Index + Middle up",
        diagram_key="draw",
    ),
    GestureCard(
        id="shapes",
        tag="CREATE",
        title="Shape Tools & Colors",
        pose="Select tool with 1 finger, draw with 2",
        description="Hover over LINE, CIRCLE, or SQUARE tools. With a shape tool active, draw with 2 fingers to set origin and expand size.",
        note="6 Colors: Blue, Green, Red, Yellow, Purple, White. Hover to switch.",
        shortcut="Line / Circle / Square",
        diagram_key="shapes",
    ),
    GestureCard(
        id="erase",
        tag="ERASE",
        title="Touchless Eraser",
        pose="Closed Fist OR 3 Fingers Up",
        description="Make a closed fist or extend 3 fingers (Index + Mid + Ring). A yellow eraser circle wipes any stroke or shape it touches.",
        note="Instant eraser gesture — no tool selection required.",
        shortcut="Fist / 3 Fingers",
        diagram_key="erase",
    ),
    GestureCard(
        id="translate",
        tag="MOVE",
        title="Move Canvas Artwork",
        pose="Open Palm (5) OR Horns (Index+Pinky)",
        description="Open your hand or make the horns gesture. Move your hand across the frame to shift and translate all existing drawings.",
        note="Release pose to drop artwork in place.",
        shortcut="Open Palm / Horns",
        diagram_key="translate",
    ),
    GestureCard(
        id="clear_and_keys",
        tag="CANVAS & KEYS",
        title="Clear Canvas & Shortcuts",
        pose="Hold on CLEAR for 25 frames (~0.8s)",
        description="Deliberate dwell hold prevents accidental clears. Full Undo/Redo is supported for all drawing and clear actions.",
        note="[Z] Undo  [Y] Redo  [S] Save  [B] Background  [T] Tutorial",
        shortcut="Hold CLEAR / Key shortcuts",
        diagram_key="clear_shortcuts",
    ),
]

# Map card IDs for quick lookup
GESTURE_MAP: Dict[str, GestureCard] = {card.id: card for card in GESTURE_DEFINITIONS}

# Multi-step tutorial progression
ONBOARDING_STEPS = [
    {
        "title": "Navigate & Draw",
        "pill": "01 · Navigate & Draw",
        "description": "Learn the essential cursor navigation and drawing gestures.",
        "cards": ["hover", "draw"],
    },
    {
        "title": "Tools & Erase",
        "pill": "02 · Tools & Erase",
        "description": "Select shape primitives, switch palette colors, and erase strokes.",
        "cards": ["shapes", "erase"],
    },
    {
        "title": "Move & Shortcuts",
        "pill": "03 · Move & Shortcuts",
        "description": "Translate drawings across canvas, dwell to clear, and quick keys.",
        "cards": ["translate", "clear_and_keys"],
    },
]


def draw_rounded_rect(
    img: np.ndarray,
    top_left: Tuple[int, int],
    bottom_right: Tuple[int, int],
    color: Tuple[int, int, int],
    thickness: int = -1,
    radius: int = 8,
) -> None:
    """Draw a rectangle with rounded corners using OpenCV primitives."""
    x1, y1 = top_left
    x2, y2 = bottom_right
    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return

    radius = min(radius, w // 2, h // 2)
    if radius <= 0:
        cv.rectangle(img, top_left, bottom_right, color, thickness)
        return

    if thickness == -1:
        # Fill center and edges
        cv.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        # 4 Corner circles
        cv.circle(img, (x1 + radius, y1 + radius), radius, color, -1, cv.LINE_AA)
        cv.circle(img, (x2 - radius, y1 + radius), radius, color, -1, cv.LINE_AA)
        cv.circle(img, (x1 + radius, y2 - radius), radius, color, -1, cv.LINE_AA)
        cv.circle(img, (x2 - radius, y2 - radius), radius, color, -1, cv.LINE_AA)
    else:
        # Outline arcs
        cv.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness, cv.LINE_AA)
        cv.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness, cv.LINE_AA)
        cv.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness, cv.LINE_AA)
        cv.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness, cv.LINE_AA)
        # Straight segments
        cv.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness, cv.LINE_AA)
        cv.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness, cv.LINE_AA)
        cv.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness, cv.LINE_AA)
        cv.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness, cv.LINE_AA)


# ---------------------------------------------------------------------------
# Procedural Gesture Illustrations (Vector-like OpenCV drawings)
# ---------------------------------------------------------------------------

def draw_hover_diagram(canvas: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    """Render procedural diagram: 1 Finger Extended with cursor target ring."""
    # Background panel
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (22, 22, 28), -1, radius=6)
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (45, 45, 55), 1, radius=6)

    cx = x + w // 2
    base_y = y + h - 16

    # Palm outline
    palm_top = base_y - 30
    draw_rounded_rect(canvas, (cx - 16, palm_top), (cx + 16, base_y), (140, 140, 150), -1, radius=4)

    # Curled thumb (left), curled middle, ring, pinky (right)
    cv.circle(canvas, (cx - 18, palm_top + 14), 6, (120, 120, 130), -1, cv.LINE_AA)
    cv.rectangle(canvas, (cx - 2, palm_top), (cx + 14, palm_top + 12), (110, 110, 120), -1)

    # Index finger extended UP
    index_tip_y = palm_top - 24
    cv.line(canvas, (cx - 8, palm_top), (cx - 8, index_tip_y), (220, 220, 230), 6, cv.LINE_AA)
    cv.circle(canvas, (cx - 8, index_tip_y), 4, (255, 255, 255), -1, cv.LINE_AA)

    # Target rings around index tip (Hover cursor)
    cv.circle(canvas, (cx - 8, index_tip_y), 9, (255, 180, 50), 1, cv.LINE_AA)
    cv.circle(canvas, (cx - 8, index_tip_y), 15, (255, 180, 50), 1, cv.LINE_AA)
    cv.line(canvas, (cx - 8 - 18, index_tip_y), (cx - 8 + 18, index_tip_y), (255, 180, 50), 1, cv.LINE_AA)
    cv.line(canvas, (cx - 8, index_tip_y - 18), (cx - 8, index_tip_y + 18), (255, 180, 50), 1, cv.LINE_AA)


def draw_draw_diagram(canvas: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    """Render procedural diagram: 2 Fingers Extended (Index + Middle) painting a stroke."""
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (22, 22, 28), -1, radius=6)
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (45, 45, 55), 1, radius=6)

    cx = x + w // 2 - 8
    base_y = y + h - 16
    palm_top = base_y - 28

    # Palm outline
    draw_rounded_rect(canvas, (cx - 14, palm_top), (cx + 16, base_y), (140, 140, 150), -1, radius=4)

    # Index and Middle fingers extended UP together
    tip_y = palm_top - 24
    cv.line(canvas, (cx - 6, palm_top), (cx - 6, tip_y), (220, 220, 230), 5, cv.LINE_AA)
    cv.line(canvas, (cx + 3, palm_top), (cx + 3, tip_y), (220, 220, 230), 5, cv.LINE_AA)
    cv.circle(canvas, (cx - 6, tip_y), 3, (255, 255, 255), -1, cv.LINE_AA)
    cv.circle(canvas, (cx + 3, tip_y), 3, (255, 255, 255), -1, cv.LINE_AA)

    # Active drawing brush stroke trailing behind
    pts = np.array([
        (cx - 1, tip_y),
        (cx + 18, tip_y - 10),
        (cx + 36, tip_y + 6),
        (cx + 52, tip_y - 4),
    ], np.int32)
    cv.polylines(canvas, [pts], False, (255, 140, 0), 3, cv.LINE_AA)  # Glowing cyan/blue stroke
    cv.circle(canvas, (cx - 1, tip_y), 5, (0, 220, 255), -1, cv.LINE_AA)


def draw_shapes_diagram(canvas: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    """Render procedural diagram: Line, Circle, Square tool shapes + color dots."""
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (22, 22, 28), -1, radius=6)
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (45, 45, 55), 1, radius=6)

    cy = y + h // 2 - 10

    # Line tool
    cv.line(canvas, (x + 14, cy + 10), (x + 36, cy - 12), (0, 255, 0), 2, cv.LINE_AA)
    cv.circle(canvas, (x + 14, cy + 10), 3, (255, 255, 255), -1, cv.LINE_AA)
    cv.circle(canvas, (x + 36, cy - 12), 3, (255, 255, 255), -1, cv.LINE_AA)

    # Circle tool
    cv.circle(canvas, (x + 60, cy), 14, (255, 0, 0), 2, cv.LINE_AA)
    cv.circle(canvas, (x + 60, cy), 2, (255, 255, 255), -1, cv.LINE_AA)

    # Square tool
    cv.rectangle(canvas, (x + 84, cy - 13), (x + 110, cy + 13), (180, 180, 180), 2, cv.LINE_AA)

    # 6 Color swatches underneath
    colors = [
        (255, 0, 0),    # Blue
        (0, 255, 0),    # Green
        (0, 0, 255),    # Red
        (0, 255, 255),  # Yellow
        (255, 0, 255),  # Purple
        (255, 255, 255) # White
    ]
    swatch_y = y + h - 14
    for idx, c in enumerate(colors):
        sx = x + 18 + idx * 17
        cv.circle(canvas, (sx, swatch_y), 5, c, -1, cv.LINE_AA)
        cv.circle(canvas, (sx, swatch_y), 5, (40, 40, 40), 1, cv.LINE_AA)


def draw_erase_diagram(canvas: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    """Render procedural diagram: Closed fist inside circular yellow eraser radius."""
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (22, 22, 28), -1, radius=6)
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (45, 45, 55), 1, radius=6)

    cx = x + w // 2
    cy = y + h // 2

    # Yellow eraser circle radius
    cv.circle(canvas, (cx, cy), 26, (0, 255, 255), 1, cv.LINE_AA)
    # Dashed-style accent ring
    cv.circle(canvas, (cx, cy), 23, (0, 200, 200), 1, cv.LINE_AA)

    # Closed fist outline
    draw_rounded_rect(canvas, (cx - 14, cy - 12), (cx + 14, cy + 14), (160, 160, 170), -1, radius=6)
    # Knuckles / finger curl lines
    cv.line(canvas, (cx - 8, cy - 5), (cx - 8, cy + 7), (90, 90, 100), 1, cv.LINE_AA)
    cv.line(canvas, (cx - 1, cy - 5), (cx - 1, cy + 7), (90, 90, 100), 1, cv.LINE_AA)
    cv.line(canvas, (cx + 6, cy - 5), (cx + 6, cy + 7), (90, 90, 100), 1, cv.LINE_AA)

    # Eraser wipe marks outside fist
    cv.line(canvas, (cx + 16, cy - 14), (cx + 24, cy - 18), (0, 255, 255), 2, cv.LINE_AA)
    cv.line(canvas, (cx - 24, cy + 16), (cx - 16, cy + 12), (0, 255, 255), 2, cv.LINE_AA)


def draw_translate_diagram(canvas: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    """Render procedural diagram: Open Palm (5 fingers) with 4-way translation cross."""
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (22, 22, 28), -1, radius=6)
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (45, 45, 55), 1, radius=6)

    cx = x + w // 2
    cy = y + h // 2

    # 4-way directional translation arrows
    arrow_color = (0, 220, 255)
    # Left-Right
    cv.arrowedLine(canvas, (cx - 4, cy), (cx - 36, cy), arrow_color, 1, cv.LINE_AA, tipLength=0.28)
    cv.arrowedLine(canvas, (cx + 4, cy), (cx + 36, cy), arrow_color, 1, cv.LINE_AA, tipLength=0.28)
    # Up-Down
    cv.arrowedLine(canvas, (cx, cy - 4), (cx, cy - 28), arrow_color, 1, cv.LINE_AA, tipLength=0.32)
    cv.arrowedLine(canvas, (cx, cy + 4), (cx, cy + 28), arrow_color, 1, cv.LINE_AA, tipLength=0.32)

    # Open hand palm
    draw_rounded_rect(canvas, (cx - 12, cy - 10), (cx + 12, cy + 14), (170, 170, 180), -1, radius=4)
    # 5 Extended fingers
    cv.line(canvas, (cx - 14, cy - 2), (cx - 20, cy - 12), (180, 180, 190), 3, cv.LINE_AA) # Thumb
    cv.line(canvas, (cx - 8, cy - 10), (cx - 9, cy - 22), (200, 200, 210), 3, cv.LINE_AA)  # Index
    cv.line(canvas, (cx - 2, cy - 10), (cx - 2, cy - 25), (200, 200, 210), 3, cv.LINE_AA)  # Mid
    cv.line(canvas, (cx + 4, cy - 10), (cx + 5, cy - 22), (200, 200, 210), 3, cv.LINE_AA)  # Ring
    cv.line(canvas, (cx + 9, cy - 8), (cx + 12, cy - 18), (180, 180, 190), 3, cv.LINE_AA)  # Pinky


def draw_clear_shortcuts_diagram(canvas: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    """Render procedural diagram: 25-frame circular dwell gauge + shortcut key badges."""
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (22, 22, 28), -1, radius=6)
    draw_rounded_rect(canvas, (x, y), (x + w, y + h), (45, 45, 55), 1, radius=6)

    cx = x + 34
    cy = y + h // 2

    # Circular dwell progress meter (~80% complete)
    cv.circle(canvas, (cx, cy), 18, (50, 50, 60), 2, cv.LINE_AA)
    cv.ellipse(canvas, (cx, cy), (18, 18), -90, 0, 280, (255, 180, 50), 3, cv.LINE_AA)
    cv.putText(canvas, "CLR", (cx - 12, cy + 4), cv.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv.LINE_AA)

    # Key shortcut badges
    kx = x + 66
    keys = [("[Z]", "Undo"), ("[Y]", "Redo"), ("[S]", "Save")]
    ky = y + 16
    for key_lbl, desc in keys:
        draw_rounded_rect(canvas, (kx, ky), (kx + 22, ky + 14), (45, 45, 58), -1, radius=3)
        draw_rounded_rect(canvas, (kx, ky), (kx + 22, ky + 14), (80, 80, 100), 1, radius=3)
        cv.putText(canvas, key_lbl, (kx + 2, ky + 10), cv.FONT_HERSHEY_SIMPLEX, 0.28, (0, 220, 255), 1, cv.LINE_AA)
        cv.putText(canvas, desc, (kx + 26, ky + 10), cv.FONT_HERSHEY_SIMPLEX, 0.30, (200, 200, 210), 1, cv.LINE_AA)
        ky += 18


DIAGRAM_RENDERERS = {
    "hover": draw_hover_diagram,
    "draw": draw_draw_diagram,
    "shapes": draw_shapes_diagram,
    "erase": draw_erase_diagram,
    "translate": draw_translate_diagram,
    "clear_shortcuts": draw_clear_shortcuts_diagram,
}


# ---------------------------------------------------------------------------
# OnboardingScreen Class
# ---------------------------------------------------------------------------

class OnboardingScreen:
    """
    Renders and manages the AirDraw First-Launch Onboarding Experience.

    Features:
    - Pre-camera tutorial screen displayed before webcam initialization.
    - Clean step-by-step gesture education with interactive procedural diagrams.
    - Primary 'Start Drawing' button and secondary 'Skip Tutorial' button.
    - Working mouse hover and click events.
    - Keyboard navigation shortcuts.
    - Responsive adaptation to different window dimensions.
    """

    def __init__(
        self,
        on_start: Optional[Callable[[], None]] = None,
        on_skip: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        self.on_start = on_start
        self.on_skip = on_skip
        self.on_exit = on_exit

        self.current_step: int = 0
        self.hover_btn: Optional[str] = None
        self.buttons: Dict[str, Tuple[int, int, int, int]] = {}  # id -> (x, y, w, h)
        self.last_width: int = 960
        self.last_height: int = 600

    @property
    def total_steps(self) -> int:
        return len(ONBOARDING_STEPS)

    def next_step(self) -> None:
        """Advance to the next tutorial step, or stay on the final step."""
        if self.current_step < self.total_steps - 1:
            self.current_step += 1

    def prev_step(self) -> None:
        """Return to the previous tutorial step."""
        if self.current_step > 0:
            self.current_step -= 1

    def set_step(self, step_idx: int) -> None:
        """Jump directly to a specific step index with bounds checking."""
        self.current_step = max(0, min(step_idx, self.total_steps - 1))

    def trigger_start(self) -> None:
        """Execute the primary Start Drawing action."""
        if self.on_start:
            self.on_start()

    def trigger_skip(self) -> None:
        """Execute the secondary Skip Tutorial action."""
        if self.on_skip:
            self.on_skip()

    def trigger_exit(self) -> None:
        """Execute application exit."""
        if self.on_exit:
            self.on_exit()

    def handle_mouse(self, event: int, x: int, y: int, flags: int, param: Optional[object] = None) -> None:
        """Process OpenCV mouse events for buttons, step tabs, and cards."""
        # Find hovered button
        hit_btn = None
        for btn_id, (bx, by, bw, bh) in self.buttons.items():
            if bx <= x <= bx + bw and by <= y <= by + bh:
                hit_btn = btn_id
                break

        if event == cv.EVENT_MOUSEMOVE:
            self.hover_btn = hit_btn

        elif event == cv.EVENT_LBUTTONDOWN:
            if hit_btn == "start":
                self.trigger_start()
            elif hit_btn == "skip":
                self.trigger_skip()
            elif hit_btn == "next":
                self.next_step()
            elif hit_btn == "prev":
                self.prev_step()
            elif hit_btn and hit_btn.startswith("step_"):
                try:
                    step_num = int(hit_btn.split("_")[1])
                    self.set_step(step_num)
                except ValueError:
                    pass

    def handle_key(self, key: int) -> bool:
        """Handle keyboard shortcuts in the onboarding screen. Return False to exit."""
        if key in (13, 32):  # Enter or Space
            self.trigger_start()
            return True
        elif key in (9, ord("s"), ord("S")):  # Tab or S
            self.trigger_skip()
            return True
        elif key in (ord("n"), ord("N"), 83):  # N or Right arrow
            self.next_step()
            return True
        elif key in (ord("p"), ord("P"), 81):  # P or Left arrow
            self.prev_step()
            return True
        elif ord("1") <= key <= ord("9"):
            num = key - ord("1")
            if num < self.total_steps:
                self.set_step(num)
            return True
        elif key in (ord("q"), ord("Q"), 27):  # Q or Esc
            self.trigger_exit()
            return False

        return True

    def render(self, width: int = 960, height: int = 600) -> np.ndarray:
        """Render the complete dark-mode onboarding screen at the specified resolution."""
        self.last_width = width
        self.last_height = height
        self.buttons.clear()

        # Near-black charcoal background
        canvas = np.full((height, width, 3), (22, 22, 26), dtype=np.uint8)

        # Subtle top accent bar (amber gold)
        cv.line(canvas, (0, 0), (width - 1, 0), (255, 180, 50), 3)

        # -------------------------------------------------------------------
        # 1. Header Section
        # -------------------------------------------------------------------
        margin_x = max(24, int(width * 0.04))
        y_cursor = 24

        # Pill badge
        pill_text = "AIRDRAW  *  GESTURE-POWERED CANVAS"
        draw_rounded_rect(canvas, (margin_x, y_cursor), (margin_x + 240, y_cursor + 20), (34, 34, 42), -1, radius=4)
        draw_rounded_rect(canvas, (margin_x, y_cursor), (margin_x + 240, y_cursor + 20), (60, 60, 72), 1, radius=4)
        cv.putText(canvas, pill_text, (margin_x + 10, y_cursor + 14), cv.FONT_HERSHEY_SIMPLEX, 0.34, (255, 180, 50), 1, cv.LINE_AA)

        y_cursor += 38
        # Main Title & Heading
        cv.putText(canvas, "AirDraw", (margin_x, y_cursor), cv.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv.LINE_AA)
        cv.putText(canvas, " — Your hands. Your canvas.", (margin_x + 115, y_cursor), cv.FONT_HERSHEY_SIMPLEX, 0.75, (220, 220, 230), 1, cv.LINE_AA)

        y_cursor += 22
        cv.putText(canvas, "Create, sketch, and explore using intuitive hand gestures — no mouse required.",
                   (margin_x, y_cursor), cv.FONT_HERSHEY_SIMPLEX, 0.42, (160, 160, 172), 1, cv.LINE_AA)

        # -------------------------------------------------------------------
        # 2. Step Navigation Tabs (Center Header)
        # -------------------------------------------------------------------
        y_cursor += 26
        tab_y = y_cursor
        tab_x = margin_x
        tab_h = 28

        for idx, step_meta in enumerate(ONBOARDING_STEPS):
            tab_w = max(130, min(180, int((width - margin_x * 2 - 120) // self.total_steps)))
            tab_id = f"step_{idx}"
            self.buttons[tab_id] = (tab_x, tab_y, tab_w, tab_h)

            is_active = (idx == self.current_step)
            is_hover = (self.hover_btn == tab_id)

            if is_active:
                bg_col = (48, 48, 62)
                border_col = (255, 180, 50)
                text_col = (255, 255, 255)
            elif is_hover:
                bg_col = (38, 38, 48)
                border_col = (120, 120, 140)
                text_col = (230, 230, 230)
            else:
                bg_col = (28, 28, 34)
                border_col = (50, 50, 60)
                text_col = (160, 160, 170)

            draw_rounded_rect(canvas, (tab_x, tab_y), (tab_x + tab_w, tab_y + tab_h), bg_col, -1, radius=5)
            draw_rounded_rect(canvas, (tab_x, tab_y), (tab_x + tab_w, tab_y + tab_h), border_col, 1, radius=5)
            cv.putText(canvas, step_meta["pill"], (tab_x + 12, tab_y + 18), cv.FONT_HERSHEY_SIMPLEX, 0.38, text_col, 1, cv.LINE_AA)

            tab_x += tab_w + 10

        # Step Prev / Next small buttons
        nav_btn_w = 60
        prev_x = max(tab_x + 10, width - margin_x - nav_btn_w * 2 - 8)
        next_x = prev_x + nav_btn_w + 8

        self.buttons["prev"] = (prev_x, tab_y, nav_btn_w, tab_h)
        self.buttons["next"] = (next_x, tab_y, nav_btn_w, tab_h)

        prev_hover = (self.hover_btn == "prev")
        next_hover = (self.hover_btn == "next")

        draw_rounded_rect(canvas, (prev_x, tab_y), (prev_x + nav_btn_w, tab_y + tab_h),
                          (38, 38, 48) if prev_hover else (28, 28, 34), -1, radius=4)
        draw_rounded_rect(canvas, (prev_x, tab_y), (prev_x + nav_btn_w, tab_y + tab_h),
                          (120, 120, 140) if prev_hover else (50, 50, 60), 1, radius=4)
        cv.putText(canvas, "< Prev", (prev_x + 8, tab_y + 18), cv.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 210), 1, cv.LINE_AA)

        draw_rounded_rect(canvas, (next_x, tab_y), (next_x + nav_btn_w, tab_y + tab_h),
                          (38, 38, 48) if next_hover else (28, 28, 34), -1, radius=4)
        draw_rounded_rect(canvas, (next_x, tab_y), (next_x + nav_btn_w, tab_y + tab_h),
                          (120, 120, 140) if next_hover else (50, 50, 60), 1, radius=4)
        cv.putText(canvas, "Next >", (next_x + 8, tab_y + 18), cv.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 210), 1, cv.LINE_AA)

        # -------------------------------------------------------------------
        # 3. Center Section: Active Gesture Cards
        # -------------------------------------------------------------------
        y_cursor += tab_h + 18
        active_step_data = ONBOARDING_STEPS[self.current_step]
        step_card_ids = active_step_data["cards"]

        # Footer height and layout bounds
        footer_height = 80
        content_bottom = height - footer_height - 10
        available_card_h = max(140, content_bottom - y_cursor)

        card_gap = 16
        # Decide 1 or 2 columns based on available width
        num_cols = 2 if width >= 680 else 1
        num_cards = len(step_card_ids)

        if num_cols == 2:
            card_w = (width - margin_x * 2 - card_gap) // 2
            card_h = available_card_h
        else:
            card_w = width - margin_x * 2
            card_h = (available_card_h - card_gap) // max(1, num_cards)

        for c_idx, card_id in enumerate(step_card_ids):
            card = GESTURE_MAP.get(card_id)
            if not card:
                continue

            if num_cols == 2:
                cx1 = margin_x + c_idx * (card_w + card_gap)
                cy1 = y_cursor
            else:
                cx1 = margin_x
                cy1 = y_cursor + c_idx * (card_h + card_gap)

            cx2 = cx1 + card_w
            cy2 = cy1 + card_h

            # Card panel
            card_bg = (30, 30, 38)
            card_border = (55, 55, 68)
            draw_rounded_rect(canvas, (cx1, cy1), (cx2, cy2), card_bg, -1, radius=8)
            draw_rounded_rect(canvas, (cx1, cy1), (cx2, cy2), card_border, 1, radius=8)

            # Left/Top diagram box
            diag_w = min(120, max(85, int(card_w * 0.28)))
            diag_h = min(100, max(65, card_h - 32))
            diag_x = cx1 + 14
            diag_y = cy1 + (card_h - diag_h) // 2

            renderer = DIAGRAM_RENDERERS.get(card.diagram_key)
            if renderer:
                renderer(canvas, diag_x, diag_y, diag_w, diag_h)

            # Text content to right of diagram
            tx = diag_x + diag_w + 16
            max_text_w = cx2 - tx - 14
            curr_ty = cy1 + 24

            # Tag badge
            badge_text = card.tag
            draw_rounded_rect(canvas, (tx, curr_ty - 13), (tx + 75, curr_ty + 4), (40, 40, 52), -1, radius=3)
            cv.putText(canvas, badge_text, (tx + 6, curr_ty), cv.FONT_HERSHEY_SIMPLEX, 0.32, (0, 220, 255), 1, cv.LINE_AA)

            curr_ty += 20
            # Card title
            cv.putText(canvas, card.title, (tx, curr_ty), cv.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv.LINE_AA)

            curr_ty += 20
            # Hand Pose
            cv.putText(canvas, f"Pose: {card.pose}", (tx, curr_ty), cv.FONT_HERSHEY_SIMPLEX, 0.40, (255, 180, 50), 1, cv.LINE_AA)

            curr_ty += 18
            # Description (word wrapped if needed)
            desc_words = card.description.split(" ")
            line1 = ""
            line2 = ""
            for word in desc_words:
                test_line = f"{line1} {word}".strip()
                size, _ = cv.getTextSize(test_line, cv.FONT_HERSHEY_SIMPLEX, 0.36, 1)
                if size[0] < max_text_w:
                    line1 = test_line
                else:
                    line2 = f"{line2} {word}".strip()

            cv.putText(canvas, line1, (tx, curr_ty), cv.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 210), 1, cv.LINE_AA)
            if line2:
                curr_ty += 16
                cv.putText(canvas, line2, (tx, curr_ty), cv.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 210), 1, cv.LINE_AA)

            curr_ty += 18
            # Note / detail
            note_str = f"- {card.note}"
            cv.putText(canvas, note_str, (tx, curr_ty), cv.FONT_HERSHEY_SIMPLEX, 0.33, (140, 140, 150), 1, cv.LINE_AA)

        # -------------------------------------------------------------------
        # 4. Bottom Controls Section (Anchored to window bottom)
        # -------------------------------------------------------------------
        divider_y = height - footer_height + 5
        cv.line(canvas, (margin_x, divider_y), (width - margin_x, divider_y), (40, 40, 50), 1)

        btn_y = divider_y + 18
        btn_h = 40

        # Skip Tutorial Button (Secondary, visible at bottom)
        skip_w = max(140, int(width * 0.16))
        skip_x = margin_x
        self.buttons["skip"] = (skip_x, btn_y, skip_w, btn_h)

        is_skip_hover = (self.hover_btn == "skip")
        skip_bg = (45, 45, 58) if is_skip_hover else (32, 32, 40)
        skip_border = (160, 160, 180) if is_skip_hover else (80, 80, 95)
        skip_txt_col = (255, 255, 255) if is_skip_hover else (210, 210, 220)

        draw_rounded_rect(canvas, (skip_x, btn_y), (skip_x + skip_w, btn_y + btn_h), skip_bg, -1, radius=6)
        draw_rounded_rect(canvas, (skip_x, btn_y), (skip_x + skip_w, btn_y + btn_h), skip_border, 1, radius=6)
        cv.putText(canvas, "Skip Tutorial", (skip_x + 18, btn_y + 25), cv.FONT_HERSHEY_SIMPLEX, 0.44, skip_txt_col, 1, cv.LINE_AA)

        # Start Drawing Button (Primary, high-contrast amber/gold)
        start_w = max(170, int(width * 0.20))
        start_x = width - margin_x - start_w
        self.buttons["start"] = (start_x, btn_y, start_w, btn_h)

        is_start_hover = (self.hover_btn == "start")
        start_bg = (255, 205, 80) if is_start_hover else (255, 180, 50)
        start_border = (255, 235, 140) if is_start_hover else (255, 180, 50)

        draw_rounded_rect(canvas, (start_x, btn_y), (start_x + start_w, btn_y + btn_h), start_bg, -1, radius=6)
        draw_rounded_rect(canvas, (start_x, btn_y), (start_x + start_w, btn_y + btn_h), start_border, 2, radius=6)
        cv.putText(canvas, "Start Drawing ->", (start_x + 20, btn_y + 25), cv.FONT_HERSHEY_SIMPLEX, 0.48, (18, 18, 22), 2, cv.LINE_AA)

        # Help reopen hint (Centered between buttons)
        hint_str = "You can reopen this guide anytime from Help (press [H] or [T])."
        hint_size, _ = cv.getTextSize(hint_str, cv.FONT_HERSHEY_SIMPLEX, 0.36, 1)
        hint_x = (width - hint_size[0]) // 2
        hint_y = btn_y + 25
        # Draw hint only if it doesn't overlap with buttons
        if hint_x > skip_x + skip_w + 10 and hint_x + hint_size[0] < start_x - 10:
            cv.putText(canvas, hint_str, (hint_x, hint_y), cv.FONT_HERSHEY_SIMPLEX, 0.36, (140, 140, 150), 1, cv.LINE_AA)

        return canvas


# ---------------------------------------------------------------------------
# CameraErrorScreen Class
# ---------------------------------------------------------------------------

class CameraErrorScreen:
    """
    Renders and manages the camera initialization failure screen with recovery options.
    """

    def __init__(
        self,
        on_retry: Optional[Callable[[], None]] = None,
        on_back_to_guide: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        self.on_retry = on_retry
        self.on_back_to_guide = on_back_to_guide
        self.on_exit = on_exit

        self.error_message: str = "Webcam could not be opened."
        self.hover_btn: Optional[str] = None
        self.buttons: Dict[str, Tuple[int, int, int, int]] = {}

    def set_error_message(self, msg: str) -> None:
        self.error_message = msg

    def handle_mouse(self, event: int, x: int, y: int, flags: int, param: Optional[object] = None) -> None:
        hit_btn = None
        for btn_id, (bx, by, bw, bh) in self.buttons.items():
            if bx <= x <= bx + bw and by <= y <= by + bh:
                hit_btn = btn_id
                break

        if event == cv.EVENT_MOUSEMOVE:
            self.hover_btn = hit_btn
        elif event == cv.EVENT_LBUTTONDOWN:
            if hit_btn == "retry" and self.on_retry:
                self.on_retry()
            elif hit_btn == "guide" and self.on_back_to_guide:
                self.on_back_to_guide()
            elif hit_btn == "exit" and self.on_exit:
                self.on_exit()

    def handle_key(self, key: int) -> bool:
        if key in (ord("r"), ord("R")):
            if self.on_retry:
                self.on_retry()
            return True
        elif key in (ord("b"), ord("B")):
            if self.on_back_to_guide:
                self.on_back_to_guide()
            return True
        elif key in (ord("q"), ord("Q"), 27):
            if self.on_exit:
                self.on_exit()
            return False
        return True

    def render(self, width: int = 960, height: int = 600, error_message: Optional[str] = None) -> np.ndarray:
        """Render the camera error recovery dialog."""
        if error_message:
            self.error_message = error_message

        self.buttons.clear()
        canvas = np.full((height, width, 3), (20, 20, 24), dtype=np.uint8)

        # Modal dimensions
        card_w = min(560, width - 40)
        card_h = min(360, height - 60)
        cx1 = (width - card_w) // 2
        cy1 = (height - card_h) // 2
        cx2 = cx1 + card_w
        cy2 = cy1 + card_h

        # Modal panel
        draw_rounded_rect(canvas, (cx1, cy1), (cx2, cy2), (28, 28, 36), -1, radius=10)
        draw_rounded_rect(canvas, (cx1, cy1), (cx2, cy2), (60, 60, 220), 2, radius=10)  # Warning border

        # Warning icon (triangle with exclamation mark)
        icon_x = cx1 + 28
        icon_y = cy1 + 42
        pts = np.array([
            (icon_x + 14, icon_y - 16),
            (icon_x, icon_y + 14),
            (icon_x + 28, icon_y + 14),
        ], np.int32)
        cv.polylines(canvas, [pts], True, (0, 180, 255), 2, cv.LINE_AA)
        cv.putText(canvas, "!", (icon_x + 11, icon_y + 8), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 180, 255), 2, cv.LINE_AA)

        # Title
        cv.putText(canvas, "Camera Initialization Failed", (icon_x + 40, icon_y + 4),
                   cv.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv.LINE_AA)

        cv.line(canvas, (cx1 + 24, cy1 + 70), (cx2 - 24, cy1 + 70), (55, 55, 68), 1)

        # Error details
        curr_y = cy1 + 98
        cv.putText(canvas, f"Error: {self.error_message}", (cx1 + 28, curr_y),
                   cv.FONT_HERSHEY_SIMPLEX, 0.40, (230, 120, 120), 1, cv.LINE_AA)

        curr_y += 28
        cv.putText(canvas, "Troubleshooting steps:", (cx1 + 28, curr_y),
                   cv.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv.LINE_AA)

        troubleshoot_lines = [
            "- Verify your webcam is plugged in and recognized by your OS.",
            "- Check camera permissions (macOS Privacy & Security / Windows Settings).",
            "- Ensure no other app (Zoom, Teams, Photo Booth) is using the camera.",
            "- You can return to the Gesture Guide while troubleshooting.",
        ]
        curr_y += 18
        for line in troubleshoot_lines:
            cv.putText(canvas, line, (cx1 + 28, curr_y), cv.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 190), 1, cv.LINE_AA)
            curr_y += 20

        # Action buttons
        btn_y = cy2 - 60
        btn_h = 38

        # 1. Retry Camera (Primary)
        retry_w = 140
        retry_x = cx1 + 28
        self.buttons["retry"] = (retry_x, btn_y, retry_w, btn_h)
        is_retry_h = (self.hover_btn == "retry")
        draw_rounded_rect(canvas, (retry_x, btn_y), (retry_x + retry_w, btn_y + btn_h),
                          (255, 205, 80) if is_retry_h else (255, 180, 50), -1, radius=5)
        cv.putText(canvas, "Retry Camera [R]", (retry_x + 12, btn_y + 24),
                   cv.FONT_HERSHEY_SIMPLEX, 0.40, (18, 18, 22), 2, cv.LINE_AA)

        # 2. Back to Guide
        guide_w = 140
        guide_x = retry_x + retry_w + 14
        self.buttons["guide"] = (guide_x, btn_y, guide_w, btn_h)
        is_guide_h = (self.hover_btn == "guide")
        draw_rounded_rect(canvas, (guide_x, btn_y), (guide_x + guide_w, btn_y + btn_h),
                          (48, 48, 62) if is_guide_h else (34, 34, 44), -1, radius=5)
        draw_rounded_rect(canvas, (guide_x, btn_y), (guide_x + guide_w, btn_y + btn_h),
                          (120, 120, 140) if is_guide_h else (60, 60, 75), 1, radius=5)
        cv.putText(canvas, "Back to Guide [B]", (guide_x + 10, btn_y + 24),
                   cv.FONT_HERSHEY_SIMPLEX, 0.38, (230, 230, 230), 1, cv.LINE_AA)

        # 3. Exit AirDraw
        exit_w = 110
        exit_x = cx2 - exit_w - 28
        self.buttons["exit"] = (exit_x, btn_y, exit_w, btn_h)
        is_exit_h = (self.hover_btn == "exit")
        draw_rounded_rect(canvas, (exit_x, btn_y), (exit_x + exit_w, btn_y + btn_h),
                          (48, 28, 28) if is_exit_h else (36, 24, 24), -1, radius=5)
        draw_rounded_rect(canvas, (exit_x, btn_y), (exit_x + exit_w, btn_y + btn_h),
                          (180, 80, 80) if is_exit_h else (100, 50, 50), 1, radius=5)
        cv.putText(canvas, "Exit [Q]", (exit_x + 20, btn_y + 24),
                   cv.FONT_HERSHEY_SIMPLEX, 0.40, (230, 140, 140), 1, cv.LINE_AA)

        return canvas
