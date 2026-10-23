import cv2 as cv
import numpy as np

from hands import Gesture
from util import xy_euclidean_dist, clamp

from enum import Enum
from history import (
    DrawingHistory,
    AddLineCommand,
    AddCircleCommand,
    AddSquareCommand,
    EraseCommand,
    ClearCanvasCommand,
)

class Color(Enum):
    """Please remember these are in BGR coordinates!"""
    GRAY = (122, 122, 122)
    WHITE = (255, 255, 255)
    BLUE = (255,0,0)
    GREEN =(0,255,0)
    RED = (0,0,255)
    PURPLE = (255, 0, 255)
    YELLOW = (0, 255, 255)

class Shape(Enum):
    CIRCLE = Color.BLUE
    SQUARE = Color.GRAY
    LINE = Color.GREEN

class Canvas:
    """ 
    This class is responsible for "drawing" all state onto the screen. 
    This includes the actual dashboard hands interact with as well as lines, backgrounds, etc.

    This component is intended to take (frame, hands_state) -> (update state) -> image to render
    """
    def __init__(self, height=480, width=640, rows=None, columns=None):
        # Support both (height, width) and legacy (rows, columns)
        if rows is not None:
            height = rows
        if columns is not None:
            width = columns

        self.height = height
        self.width = width
        self.rows = height
        self.columns = width

        self.colors = [ Color.BLUE, Color.GREEN, Color.RED, Color.YELLOW, Color.PURPLE, Color.WHITE ]
        self.shapes = [ Shape.LINE, Shape.CIRCLE, Shape.SQUARE ]
        self.color = Color.BLUE # only really used to initialize lines
        self.shape = Shape.LINE
        self.lines = {} # map of origin -> Line
        self.circles = [] # list of Circle objects
        self.squares = [] # list of Square objects
        self.brush_size = 5
        self.history = DrawingHistory()
        self.currLine = Line(self.color, None, thickness=self.brush_size) # this is the line we're adding to 
        self.currLine.active = False
        self.currCircle = Circle((-1, -1), -1, self.color, thickness=self.brush_size)
        self.currCircle.active = False
        self.currSquare = Square((-1, -1), (-1, -1), self.color, thickness=self.brush_size)
        self.currSquare.active = False
        self.blackout_background = False
        self.clear_dwell_frames = 0
        self.clear_dwell_threshold = 25  # ~0.8s hold to confirm clear
        self.clear_hovering = False
        self._clear_latched = False
        self.status_message = ""
        self.status_message_frames = 0
        self.show_help = False

    def toggle_help(self):
        """Toggles the in-app interactive help overlay."""
        self.show_help = not self.show_help

    def undo(self) -> bool:
        """Undoes the last completed drawing or canvas action."""
        success = self.history.undo(self)
        if success:
            self.set_status("Undo")
        else:
            self.set_status("Nothing to undo")
        return success

    def redo(self) -> bool:
        """Redoes the last undone drawing or canvas action."""
        success = self.history.redo(self)
        if success:
            self.set_status("Redo")
        else:
            self.set_status("Nothing to redo")
        return success

    @property
    def can_undo(self) -> bool:
        return self.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self.history.can_redo

    def set_brush_size(self, size: int):
        self.brush_size = max(1, min(size, 30))
        self.set_status(f"Brush size: {self.brush_size} px")

    def set_status(self, msg: str, duration: int = 45):
        self.status_message = msg
        self.status_message_frames = duration

    def switch_background(self):
        self.blackout_background = not self.blackout_background

    def get_buttons_coords(self, frame_shape):
        """Return toolbar hitboxes in (top-left, bottom-right) screen coordinates.

        The toolbar is a single compact row so it leaves more of the camera view
        available for drawing. Ordering remains: clear, colors, then shape tools.
        """
        frame_height, frame_width = frame_shape[:2]
        margin = max(3, int(min(frame_height, frame_width) * 0.008))
        gap = max(2, int(frame_width * 0.004))
        toolbar_height = max(38, min(72, int(frame_height * 0.13)))
        clear_width = max(66, int(frame_width * 0.14))
        slots = len(self.colors) + len(self.shapes)
        slot_width = max(1, (frame_width - clear_width - margin * 2 - gap * (slots - 1)) // slots)
        top = margin
        bottom = max(top + 1, toolbar_height - margin)

        coords = []
        clear_right = min(frame_width - 1, margin + clear_width)
        coords.append((
            "CLEAR",
            (48, 48, 58),
            (margin, top),
            (clear_right, bottom),
        ))

        x = clear_right + gap
        for color in self.colors:
            right = min(frame_width - 1, x + slot_width)
            coords.append((
                color.name,
                color.value,
                (x, top),
                (right, bottom),
            ))
            x = right + gap

        for shape in self.shapes:
            right = min(frame_width - 1, x + slot_width)
            coords.append((
                shape.name,
                (48, 48, 58),
                (x, top),
                (right, bottom),
            ))
            x = right + gap

        return coords

    def buttons_overlap(self, buttons_coords, fingertip_point):
        if fingertip_point is None:
            return False
        leftCoord, topCoord = buttons_coords[0]
        rightCoord, bottomCoord = buttons_coords[1]

        r, c = fingertip_point
        return leftCoord <= c <= rightCoord and topCoord <= r <= bottomCoord

    def update_state(self, frame_shape, data=None):
        """
        Takes in state updates from hands and updates internal canvas state.
        Safely stops drawing when hand tracking is lost and protects against accidental actions.
        """
        data = data or {}
        if not data or data.get('tracking') is False:
            self.end_drawing()
            self.clear_dwell_frames = 0
            self.clear_hovering = False
            self._clear_latched = False
            return

        gesture = data.get("gesture", Gesture.NONE)
        if gesture == Gesture.NONE:
            self.end_drawing()
            self.clear_dwell_frames = 0
            self.clear_hovering = False
            self._clear_latched = False
            return

        buttons_coord = self.get_buttons_coords(frame_shape)
        clear_button = buttons_coord[0]
        button_offset = 1
        color_buttons = buttons_coord[button_offset:button_offset+len(self.colors)]
        button_offset += len(self.colors)
        shape_buttons = buttons_coord[button_offset:button_offset+len(Shape)]

        # Deliberate interaction: only index finger pointing in HOVER mode activates UI buttons
        cursor_coord = data.get('idx_fing_tip')
        if gesture == Gesture.HOVER and cursor_coord is not None:
            # Overlap with Clear All button (requires holding for dwell confirmation)
            if self.buttons_overlap(clear_button[2:], cursor_coord):
                self.clear_hovering = True
                if not self._clear_latched:
                    self.clear_dwell_frames += 1
                    if self.clear_dwell_frames >= self.clear_dwell_threshold:
                        self.end_drawing()
                        if self.lines or self.circles or self.squares:
                            self.history.push(ClearCanvasCommand(self.lines, self.circles, self.squares))
                        self.lines = {}
                        self.circles = []
                        self.squares = []
                        self.clear_dwell_frames = self.clear_dwell_threshold
                        self._clear_latched = True
                        self.set_status("Canvas cleared - Undo available")
            else:
                self.clear_dwell_frames = 0
                self.clear_hovering = False
                self._clear_latched = False

            # Apply a tool change only when the cursor enters a different control.
            # This avoids repeating the same status message on every video frame.
            hover_target = None
            for color_button_metadata in color_buttons:
                button_color_str = color_button_metadata[0]
                if self.buttons_overlap(color_button_metadata[2:], cursor_coord):
                    hover_target = ("color", button_color_str)
                    if self.color.name != button_color_str:
                        self.color = Color[button_color_str]
                        self.set_status(f"Color set to {self.color.name}")
                    break

            if hover_target is None:
                for shape_button_metadata in shape_buttons:
                    shape_str = shape_button_metadata[0]
                    if self.buttons_overlap(shape_button_metadata[2:], cursor_coord):
                        hover_target = ("shape", shape_str)
                        if self.shape.name != shape_str:
                            self.shape = Shape[shape_str]
                            self.set_status(f"Tool set to {self.shape.name}")
                        break

        else:
            self.clear_dwell_frames = 0
            self.clear_hovering = False
            self._clear_latched = False

        # Execute gesture actions
        origin = data.get('origin')
        if gesture == Gesture.DRAW and origin is not None:
            midpoint_r, midpoint_c = origin

            if self.shape == Shape.LINE:
                self.push_point((midpoint_r, midpoint_c))
            elif self.shape == Shape.CIRCLE:
                self.update_circle((midpoint_r, midpoint_c))
            elif self.shape == Shape.SQUARE:
                self.update_square((midpoint_r, midpoint_c))

        elif gesture == Gesture.HOVER:
            self.end_drawing()

        elif gesture == Gesture.ERASE and origin is not None:
            self.end_drawing()
            midpoint_r, midpoint_c = origin
            radius = int(data.get('radius', 25))
            self.erase_mode((midpoint_r, midpoint_c), radius)

        elif gesture == Gesture.TRANSLATE and origin is not None:
            self.end_drawing()
            midpoint_r, midpoint_c = origin
            radius = int(data.get('radius', 30))
            shift = data.get('shift', (0, 0))
            if shift is not None:
                shift = int(shift[0]), int(shift[1])
                self.translate_mode((midpoint_r, midpoint_c), radius, shift)
    
    def draw_canvas(self, frame, data):
        """Render the camera/whiteboard, compact toolbar, artwork, cursor and status."""
        data = data or {}
        if self.blackout_background:
            frame = np.zeros_like(frame)

        frame_height, frame_width = frame.shape[:2]

        # Render artwork first so the toolbar remains readable above it.
        frame = self.draw_lines(frame)
        frame = self.draw_circles(frame)
        frame = self.draw_squares(frame)
        buttons_coord = self.get_buttons_coords(frame.shape)
        toolbar_bottom = min(frame_height - 1, max(38, min(72, int(frame_height * 0.13))))
        toolbar_overlay = frame.copy()
        cv.rectangle(toolbar_overlay, (0, 0), (frame_width - 1, toolbar_bottom), (24, 24, 29), -1)
        frame = cv.addWeighted(frame, 0.28, toolbar_overlay, 0.72, 0)

        for button_metadata in buttons_coord:
            button_name, button_color, top_left, bottom_right = button_metadata
            x1, y1 = top_left
            x2, y2 = bottom_right

            cv.rectangle(frame, top_left, bottom_right, button_color, -1)
            cv.rectangle(frame, top_left, bottom_right, (90, 90, 100), 1)

            # Match contrast to the color swatch for easy reading.
            if button_name in Color.__members__:
                color = Color[button_name]
                blue, green, red = color.value
                brightness = 0.114 * blue + 0.587 * green + 0.299 * red
                text_color = (25, 25, 25) if brightness > 130 else (250, 250, 250)
                selected = self.color.name == button_name
                if selected:
                    cv.rectangle(frame, (x1 + 1, y1 + 1), (x2 - 1, y2 - 1), (255, 255, 255), 2)
            elif button_name in Shape.__members__:
                text_color = (245, 245, 245)
                selected = self.shape.name == button_name
                if selected:
                    cv.rectangle(frame, (x1 + 1, y1 + 1), (x2 - 1, y2 - 1), (0, 220, 255), 2)
            else:
                text_color = (100, 100, 255)

            label = "RECT" if button_name == "SQUARE" else button_name
            max_text_width = max(8, x2 - x1 - 8)
            font_scale = 0.40
            while font_scale > 0.22:
                text_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0]
                if text_size[0] <= max_text_width:
                    break
                font_scale -= 0.02
            text_size = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0]
            text_x = x1 + max(3, (x2 - x1 - text_size[0]) // 2)
            text_y = y1 + (y2 - y1 + text_size[1]) // 2
            cv.putText(frame, label, (text_x, text_y), cv.FONT_HERSHEY_SIMPLEX,
                       font_scale, text_color, 1, cv.LINE_AA)

            if button_name == "CLEAR" and self.clear_hovering and self.clear_dwell_frames > 0:
                progress = min(1.0, self.clear_dwell_frames / self.clear_dwell_threshold)
                fill_width = int((x2 - x1) * progress)
                cv.rectangle(frame, (x1, y2 - 4), (x1 + fill_width, y2), (0, 0, 255), -1)

        tracking = data.get('tracking', False) if data else False
        gesture = data.get('gesture') if data else Gesture.NONE
        origin = data.get('origin') if data else None

        # Interactive Cursor System
        if tracking and origin is not None:
            c_r, c_c = origin
            if gesture == Gesture.HOVER:
                # Hover / Cursor pointing mode: precise target ring and dot
                cv.circle(frame, (c_c, c_r), 6, self.color.value, -1)
                cv.circle(frame, (c_c, c_r), 9, (255, 255, 255), 1)
                cv.putText(frame, "CURSOR", (c_c + 14, c_r - 6), cv.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 220), 1, cv.LINE_AA)

            elif gesture == Gesture.DRAW:
                # Drawing mode: pulsing brush radius preview
                radius = data.get('radius', 10)
                img = frame.copy()
                cv.circle(img, (c_c, c_r), int(radius), self.color.value, -1)
                frame = cv.addWeighted(frame, 0.65, img, 0.35, 0)
                cv.circle(frame, (c_c, c_r), max(2, self.brush_size // 2), (255, 255, 255), -1)
                cv.putText(frame, f"DRAW ({self.brush_size}px)", (c_c + 14, c_r - 6), cv.FONT_HERSHEY_SIMPLEX, 0.4, self.color.value, 1, cv.LINE_AA)

            elif gesture == Gesture.ERASE:
                # Erase mode: yellow translucent boundary
                radius = data.get('radius', 25)
                img = frame.copy()
                cv.circle(img, (c_c, c_r), int(radius), Color.YELLOW.value, -1)
                frame = cv.addWeighted(frame, 0.65, img, 0.35, 0)
                cv.circle(frame, (c_c, c_r), int(radius), Color.YELLOW.value, 2)
                cv.putText(frame, "ERASE", (c_c + 14, c_r - 6), cv.FONT_HERSHEY_SIMPLEX, 0.4, Color.YELLOW.value, 1, cv.LINE_AA)

            elif gesture == Gesture.TRANSLATE:
                # Translate mode: white grab ring
                radius = data.get('radius', 30)
                img = frame.copy()
                cv.circle(img, (c_c, c_r), int(radius), Color.WHITE.value, -1)
                frame = cv.addWeighted(frame, 0.65, img, 0.35, 0)
                cv.circle(frame, (c_c, c_r), int(radius), Color.WHITE.value, 2)
                cv.putText(frame, "MOVE", (c_c + 14, c_r - 6), cv.FONT_HERSHEY_SIMPLEX, 0.4, Color.WHITE.value, 1, cv.LINE_AA)

        # Compact status bar keeps the action and shortcut text from colliding
        # on common 640px-wide webcam frames.
        hud_height = max(30, min(38, int(frame_height * 0.075)))
        hud_y = frame_height - hud_height
        hud_overlay = frame.copy()
        cv.rectangle(hud_overlay, (0, hud_y), (frame_width - 1, frame_height - 1), (20, 20, 24), -1)
        frame = cv.addWeighted(frame, 0.22, hud_overlay, 0.78, 0)
        cv.line(frame, (0, hud_y), (frame_width - 1, hud_y), (70, 70, 78), 1)

        if not tracking:
            status_text = "No hand detected - move your hand into view"
            text_color = (90, 90, 255)
        elif self.status_message_frames > 0:
            status_text = self.status_message
            text_color = (0, 235, 255)
            self.status_message_frames -= 1
        else:
            status_text = f"{gesture.value}  |  {self.shape.name}  |  {self.color.name}  |  {self.brush_size}px"
            text_color = (245, 245, 245)

        shortcuts_text = "[Z] Undo  [Y] Redo  [H] Help"
        font_scale = 0.38 if frame_width >= 720 else 0.31
        status_width = cv.getTextSize(status_text, cv.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0][0]
        shortcuts_width = cv.getTextSize(shortcuts_text, cv.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0][0]
        available_status_width = max(40, frame_width - shortcuts_width - 35)
        while status_width > available_status_width and font_scale > 0.25:
            font_scale -= 0.02
            status_width = cv.getTextSize(status_text, cv.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0][0]
            shortcuts_width = cv.getTextSize(shortcuts_text, cv.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0][0]

        baseline_y = frame_height - max(8, (hud_height - 12) // 2)
        cv.putText(frame, status_text, (12, baseline_y), cv.FONT_HERSHEY_SIMPLEX,
                   font_scale, text_color, 1, cv.LINE_AA)
        cv.putText(frame, shortcuts_text, (max(12, frame_width - shortcuts_width - 12), baseline_y),
                   cv.FONT_HERSHEY_SIMPLEX, font_scale, (175, 175, 185), 1, cv.LINE_AA)

        if self.show_help:
            frame = self.draw_help_overlay(frame)

        return frame

    def draw_help_overlay(self, frame):
        """Draws a clean, centered interactive help card with gestures and shortcuts."""
        h, w, _ = frame.shape
        card_w = min(580, w - 40)
        card_h = min(370, h - 50)
        x1 = (w - card_w) // 2
        y1 = (h - card_h) // 2
        x2 = x1 + card_w
        y2 = y1 + card_h

        # Dim background slightly for focus
        dim = frame.copy()
        cv.rectangle(dim, (0, 0), (w, h), (0, 0, 0), -1)
        frame = cv.addWeighted(frame, 0.4, dim, 0.6, 0)

        # Modal card background
        card_bg = frame.copy()
        cv.rectangle(card_bg, (x1, y1), (x2, y2), (28, 28, 34), -1)
        frame = cv.addWeighted(frame, 0.15, card_bg, 0.85, 0)
        cv.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 50), 2)

        # Card Title
        cv.putText(frame, "AirDraw - Controls & Gesture Guide", (x1 + 20, y1 + 32),
                   cv.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv.LINE_AA)
        cv.putText(frame, "Press [H] or [ESC] to close", (x2 - 195, y1 + 30),
                   cv.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1, cv.LINE_AA)
        cv.line(frame, (x1 + 20, y1 + 45), (x2 - 20, y1 + 45), (70, 70, 80), 1)

        # Section 1: Gestures
        cv.putText(frame, "TOUCHLESS HAND GESTURES", (x1 + 20, y1 + 70),
                   cv.FONT_HERSHEY_SIMPLEX, 0.46, (0, 220, 255), 1, cv.LINE_AA)

        gestures = [
            ("1 Finger (Index)", "Move Cursor & Hover / Select Tools"),
            ("2 Fingers (Index+Mid)", "Draw Strokes & Shapes"),
            ("3 Fingers / Fist", "Erase elements near cursor"),
            ("Open Palm / Horns", "Translate & Move Artwork"),
            ("Hold on 'Clear all'", "Dwell timer (~0.8s) confirms wipe"),
        ]
        curr_y = y1 + 92
        for gesture_title, gesture_desc in gestures:
            cv.putText(frame, f" * {gesture_title:<22}: {gesture_desc}", (x1 + 20, curr_y),
                       cv.FONT_HERSHEY_SIMPLEX, 0.40, (230, 230, 230), 1, cv.LINE_AA)
            curr_y += 21

        # Section 2: Keyboard Shortcuts
        curr_y += 8
        cv.line(frame, (x1 + 20, curr_y), (x2 - 20, curr_y), (70, 70, 80), 1)
        curr_y += 20
        cv.putText(frame, "KEYBOARD SHORTCUTS", (x1 + 20, curr_y),
                   cv.FONT_HERSHEY_SIMPLEX, 0.46, (0, 220, 255), 1, cv.LINE_AA)

        curr_y += 22
        shortcuts = [
            ("[Z] / [Ctrl+Z]  Undo", "[Y] / [Ctrl+Y]  Redo"),
            ("[ [ / ] ]       Brush Size", "[B]            Toggle Background"),
            ("[S] / [Ctrl+S]  Save & Export PNG", "[E]            Export Transparent PNG"),
            ("[H]            Toggle Help", "[Q] / [ESC]    Quit AirDraw"),
        ]
        for col1, col2 in shortcuts:
            cv.putText(frame, f" {col1:<30} {col2}", (x1 + 20, curr_y),
                       cv.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1, cv.LINE_AA)
            curr_y += 20

        return frame
    
    def update_and_draw(self, frame, data=None):
        data = data or {}
        self.update_state(frame.shape, data)
        frame = self.draw_canvas(frame, data)
        return frame

    def update_circle(self, new_point):
        """ Maintain state of the currently drawn circle. If it doesnt exist, initialize it and pass pointer to self.circles"""
        point_row, point_col = new_point

        if not (0 <= point_row < self.rows and 0 <= point_col < self.columns):
            return
        
        if self.currCircle.active == False:
            self.currCircle = Circle((point_row, point_col), 5, self.color, thickness=self.brush_size)
            self.circles.append(self.currCircle)
        else:
            dist = int(xy_euclidean_dist(self.currCircle.origin, new_point))
            self.currCircle.radius = dist
    
    def update_square(self, new_point):
        """Updates state of the currently drawn square (resizing it). If it doesn't exist, initialize it and pass pointer to self.squares"""
        point_row, point_col = new_point

        if not (0 <= point_row < self.rows and 0 <= point_col < self.columns):
            return

        if self.currSquare.active == False:
            self.currSquare = Square(new_point, (point_row + 5, point_col + 5), self.color, thickness=self.brush_size)
            self.squares.append(self.currSquare)
        else:
            self.currSquare.opposite = new_point

    def push_point(self, point):
        """
        adds a point to draw later on

        Arguments: 
            point: (r, c) pair describing new coordinate of the line
        """

        row, col = point 
        if not 0 <= row < self.rows or not 0 <= col < self.columns:
            return

        if self.currLine.active == False:
            line = Line(self.color, point, thickness=self.brush_size)
            self.currLine = line
            self.lines[point] = self.currLine
        else:
            self.currLine.points.append(point)

    def end_drawing(self):
        """Ends active drawing and commits completed shape actions to history."""
        if getattr(self, 'currLine', None) and self.currLine.active:
            self.currLine.active = False
            if len(self.currLine.points) > 1:
                self.history.push(AddLineCommand(self.currLine))

        if getattr(self, 'currCircle', None) and self.currCircle.active:
            self.currCircle.active = False
            if self.currCircle.radius > 5:
                self.history.push(AddCircleCommand(self.currCircle))

        if getattr(self, 'currSquare', None) and self.currSquare.active:
            self.currSquare.active = False
            if self.currSquare.get_width() > 5 or self.currSquare.get_height() > 5:
                self.history.push(AddSquareCommand(self.currSquare))

    def draw_lines(self, frame):
        for line in self.lines.values():
            thick = getattr(line, 'thickness', 5)
            for i, point in enumerate(line.points):
                if i == 0:
                    continue
                prev_r, prev_c = line.points[i-1]
                r, c = point
                cv.line( 
                        frame, 
                        (prev_c, prev_r), 
                        (c, r), 
                        line.color.value,
                        thick
                        )
        return frame
    
    def draw_circles(self, frame):
        for circle in self.circles:
            orig_row, orig_col = circle.origin
            thick = getattr(circle, 'thickness', 3)
            cv.circle(frame, (orig_col, orig_row), circle.radius, circle.color.value, thick)
        return frame
    
    def draw_squares(self, frame):
        for square in self.squares:
            topRow, leftCol, bottomRow, rightCol = square.get_coords()
            thick = getattr(square, 'thickness', 5)
            frame = cv.rectangle(
                frame,
                (leftCol, topRow),
                (rightCol, bottomRow),
                square.color.value,
                thick
            )
        return frame


    def translate_mode(self, position, radius, shift):
        """
        Works as following:

        1. gather all lines in the radius
        2. for each line:
            shift each point in the line by the shift variable
        
       """
        # FIXME: introducing extra lines unnecessarily into the program

        r, c = position
        if shift == (0, 0):
            return

        # we should be able to collect all unique origin points 
        uniqueLines = set()
        for origin, line in self.lines.items():
            for p in line.points:
                if xy_euclidean_dist(p, position) <= radius:
                    uniqueLines.add(origin)
                    break
        
        # debugging line
        sortedLines = sorted(list(uniqueLines))

        # for each origin point in the circle
        for og_point in sortedLines:
            # Transform original points
            line = self.lines[og_point]
            translation = []
            for r, c in line.points:
                trans_r, trans_c = r + shift[0], c + shift[1]
                if (0 <= trans_r < self.rows) and (0 <= trans_c < self.columns):
                    translation.append((trans_r, trans_c))
                else:
                    break

            # Check if transformation is valid
            if len(translation) == len(line.points):
                self.lines.pop(og_point)
                line.points = translation
                self.lines[line.get_origin()] = line
        
        for i, circle in enumerate(self.circles):                
            if circle.overlaps_circle(position, radius):
                new_origin = (circle.origin[0] + shift[0], circle.origin[1] + shift[1])
                circle.origin = new_origin

        for i, square in enumerate(self.squares):
            if square.overlaps_circle(position, radius):
                new_anchor = square.anchor[0] + shift[0], square.anchor[1] + shift[1]
                new_opposite = square.opposite[0] + shift[0], square.opposite[1] + shift[1]
                square.anchor = new_anchor
                square.opposite = new_opposite

    # start of erase mode code
    def erase_mode(self, position, radius):
        """
        Interprets the position of the pointer, 
        deletes lines if they overlap with the pointer
        """
        origin_points = []
        removed_lines = []
        for origin, line in self.lines.items():
            for point in line.points:
                if xy_euclidean_dist(point, position) <= radius:
                    origin_points.append(origin)
                    removed_lines.append(line)
                    break

        for origin in origin_points:
            self.lines.pop(origin)

        circles_to_keep = []
        removed_circles = []
        for circle in self.circles:
            if circle.overlaps_circle(position, radius):
                removed_circles.append(circle)
            else:
                circles_to_keep.append(circle)
        self.circles = circles_to_keep

        squares_to_keep = []
        removed_squares = []
        for square in self.squares:
            if square.overlaps_circle(position, radius):
                removed_squares.append(square)
            else:
                squares_to_keep.append(square)

        self.squares = squares_to_keep

        if removed_lines or removed_circles or removed_squares:
            self.history.push(EraseCommand(removed_lines, removed_circles, removed_squares))

class Line():
    """
    Helper class to represent the lines put on the screen
    """

    def __init__(self, color: Color, origin=None, thickness: int = 5):
        self.color = color
        self.points = [origin] if origin is not None else []
        self.thickness = thickness
        self.active = True

    def get_origin(self):
        return self.points[0] if self.points else None

    def __repr__(self):
        return f"\ncolor({self.color}) \
                \n\tactive({self.active}) \
                \n\tpoints({self.points})"

class Circle():
    """Helper class to place circles on screen"""
    def __init__(self, origin, radius: int, color: Color, thickness: int = 3):
        self.origin = origin
        self.radius = radius
        self.color = color
        self.thickness = thickness
        self.active = True
    
    def get_radius(self):
        return self.radius
    
    def overlaps_circle(self, point, other_radius) -> bool:
        dist = xy_euclidean_dist(self.origin, point)
        return max(self.radius - other_radius, 0) <= dist <= self.radius + other_radius

    def __repr__(self):
        return f"Origin:{self.origin}\tRadius:{self.radius}\tColor:{self.color}"


class Square():
    def __init__(self, anchor, opposite, color: Color, thickness: int = 5):
        self.anchor = anchor
        self.opposite = opposite
        self.color = color
        self.thickness = thickness
        self.active = True

    def get_coords(self):
        topRow = min(self.anchor[0], self.opposite[0])
        bottomRow = max(self.anchor[0], self.opposite[0])
        leftCol = min(self.anchor[1], self.opposite[1])
        rightCol = max(self.anchor[1], self.opposite[1])
        return (topRow, leftCol, bottomRow, rightCol)
    
    def get_height(self):
        topRow, leftCol, bottomRow, rightCol = self.get_coords()
        return (bottomRow - topRow)

    def get_width(self):
        topRow, leftCol, bottomRow, rightCol = self.get_coords()
        return (rightCol - leftCol)

    def overlaps_circle(self, point, radius) -> bool:
        """
        Returns true if the square (boundary or interior) overlaps with the circle.
        Args:
            point: (row, col) of the query point
            radius: radius of circle
        """
        point_r, point_c = point
        topRow, leftCol, bottomRow, rightCol = self.get_coords()

        # Find closest point on rectangle to circle center
        closest_r = clamp(point_r, topRow, bottomRow)
        closest_c = clamp(point_c, leftCol, rightCol)

        dist_sq = (point_r - closest_r) ** 2 + (point_c - closest_c) ** 2
        return dist_sq <= (radius ** 2)

    def __repr__(self):
        topRow, leftCol, bottomRow, rightCol = self.get_coords()
        return f"topLeft: {(topRow, leftCol)}\tbottomRight:{(bottomRow, rightCol)}\tcolor:{self.color}"
