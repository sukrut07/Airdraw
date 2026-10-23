import cv2 as cv
import numpy as np

from hands import Gesture, HandDetector
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

# FIXME: 
# use a good spatial query system (is just iterating over literally every point the best we can do?) 
# Gauging this would need the following:
#   How many data points could i realistically collect over a 2-minute episode?
#   How much does it cost to iterate and compare versus 
#       1. storing waypoints in a grid, and then searching every pixel in the grid
#       2. Storing all points in some sort of query system (intuition screaming quadtree).
# have consistent usage of row, col convention between mediapipe, canvas, and opencv. 
# keep all data intialized at startup and only completely transform in function

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

class Canvas():
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
        self.status_message = ""
        self.status_message_frames = 0

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
        self.set_status(f"Brush Size: {self.brush_size}")

    def set_status(self, msg: str, duration: int = 45):
        self.status_message = msg
        self.status_message_frames = duration

    def switch_background(self):
        self.blackout_background = not self.blackout_background

    def get_buttons_coords(self, frame_shape):
        """
        Returns coordinates of the buttons (and colors) to draw on the UI, used to save space later on.
        Should be useful for detecting overlap between fingers and buttons.

        Args:
            frame_shape: tuple describing frame shape
        Return:
            List with elements holding the following schema: (button name, button BGR colors, top-left coordinate, bottom-right coordinate)
            Ordering of the elements is as follows:
                1. Clear all button
                2. Color buttons
                3. Shape buttons
        """

        # Obtains the proportionally correct buttons for the frame shape given. 
        frame_height, frame_width, _ = frame_shape

        coords = []

        # add clear_button
        # Clear button is manually sized, all other buttons are manually sized
        clear_button_width = int(frame_width *.2) 
        clear_button_height = int(frame_height * .15) 

        clear_button_width_border = int(clear_button_width * .05) 
        clear_button_height_border = int(clear_button_height * .05)

        coords.append(
            (
                "Clear all",
                Color.GRAY.value,
                (clear_button_width_border, clear_button_height_border), 
                (clear_button_width - clear_button_width_border, clear_button_height - clear_button_height_border)
            ))

        num_colors = len(self.colors)
        remaining_width = frame_width - clear_button_width

        color_button_width = remaining_width // num_colors 
        color_button_height = int(clear_button_height * 0.7)
        color_button_border_width = int(color_button_width * 0.05)
        color_button_border_height = int(color_button_height * 0.05)
        curr_button_offset_width = clear_button_width

        # FIXME: use color.name instead?
        for color in self.colors:
            coords.append((
                color.name,
                color.value,
                (curr_button_offset_width  + color_button_border_width, color_button_border_height),
                (curr_button_offset_width  + color_button_width - color_button_border_width, color_button_height - color_button_border_height)
            ))

            curr_button_offset_width += color_button_width
        
        num_shapes = len(Shape)
        remaining_height = frame_height - clear_button_height
        shape_button_height = (remaining_height // num_shapes)
        shape_button_width = int(clear_button_width * 0.7)
        shape_button_border_height = int(shape_button_height * 0.05)
        shape_button_border_width = int(shape_button_width * 0.05)

        curr_button_offset_height = clear_button_height

        for shape in Shape:
            coords.append((
                shape.name,
                shape.value.value,
                (shape_button_border_width, curr_button_offset_height + shape_button_border_height),
                (shape_button_width - shape_button_border_width, curr_button_offset_height + shape_button_height - shape_button_border_height)
            ))

            curr_button_offset_height += shape_button_height
        
        return coords

    def buttons_overlap(self, buttons_coords, fingertip_point):
        if fingertip_point is None:
            return False
        leftCoord, topCoord = buttons_coords[0]
        rightCoord, bottomCoord = buttons_coords[1]

        r, c = fingertip_point
        return leftCoord <= c <= rightCoord and topCoord <= r <= bottomCoord

    def update_state(self, frame_shape, data = {}):
        """
        Takes in state updates from hands and updates internal canvas state.
        Safely stops drawing when hand tracking is lost and protects against accidental actions.
        """
        if not data or data.get('tracking') is False:
            self.end_drawing()
            self.clear_dwell_frames = 0
            self.clear_hovering = False
            return

        gesture = data.get("gesture", Gesture.NONE)
        if gesture == Gesture.NONE:
            self.end_drawing()
            self.clear_dwell_frames = 0
            self.clear_hovering = False
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
                self.clear_dwell_frames += 1
                if self.clear_dwell_frames >= self.clear_dwell_threshold:
                    self.end_drawing()
                    if self.lines or self.circles or self.squares:
                        self.history.push(ClearCanvasCommand(self.lines, self.circles, self.squares))
                    self.lines = {}
                    self.circles = []
                    self.squares = []
                    self.clear_dwell_frames = 0
                    self.clear_hovering = False
                    self.set_status("Canvas Cleared (Undo available)")
            else:
                self.clear_dwell_frames = 0
                self.clear_hovering = False

            # Overlap with color buttons
            for color_button_metadata in color_buttons:
                button_color_str = color_button_metadata[0]
                if self.buttons_overlap(color_button_metadata[2:], cursor_coord):
                    new_color = [color for color in self.colors if color.name == button_color_str][0]
                    self.color = new_color
                    self.set_status(f"Color: {new_color.name}")

            # Overlap with shape buttons
            for shape_button_metadata in shape_buttons:
                shape_str = shape_button_metadata[0]
                if self.buttons_overlap(shape_button_metadata[2:], cursor_coord):
                    new_shape = [shape for shape in self.shapes if shape.name == shape_str][0]
                    self.shape = new_shape
                    self.set_status(f"Shape: {new_shape.name}")
        else:
            self.clear_dwell_frames = 0
            self.clear_hovering = False

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
        """
        Renders dashboard onto screen
        """
        if self.blackout_background:
            frame = np.zeros_like(frame)

        buttons_coord = self.get_buttons_coords(frame.shape)

        for button_metadata in buttons_coord:
            button_str = button_metadata[0]
            button_color_rgb = button_metadata[1]
            button_left, button_top = button_metadata[2]
            button_right, button_bottom = button_metadata[3]

            frame = cv.rectangle(frame, 
                                (button_left, button_top),
                                (button_right, button_bottom),
                                button_color_rgb, -1)

            button_width = button_right - button_left
            button_height = button_bottom - button_top

            cv.putText(frame, button_str, 
                    (button_left + int((button_width)* .25), int(button_top + button_height * .55)), 
                    cv.FONT_HERSHEY_SIMPLEX, .45, Color.WHITE.value, 1, cv.LINE_AA)

            # Highlight selected color or shape
            if button_str == self.color.name or button_str == self.shape.name:
                cv.rectangle(frame,
                             (button_left, button_top),
                             (button_right, button_bottom),
                             (255, 255, 255), 2)

            # Clear all dwell progress indicator
            if button_str == "Clear all" and self.clear_hovering and self.clear_dwell_frames > 0:
                progress = min(1.0, self.clear_dwell_frames / self.clear_dwell_threshold)
                fill_w = int(button_width * progress)
                cv.rectangle(frame,
                             (button_left, button_bottom - 8),
                             (button_left + fill_w, button_bottom),
                             (0, 0, 255), -1)
                cv.putText(frame, "HOLD TO CLEAR",
                           (button_left + 5, button_bottom - 12),
                           cv.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1, cv.LINE_AA)

        # Draw drawing primitives
        frame = self.draw_lines(frame)
        frame = self.draw_circles(frame)
        frame = self.draw_squares(frame)

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

        # Bottom HUD Status Bar (semi-transparent dark pill)
        hud_height = 36
        hud_y = frame.shape[0] - hud_height
        hud_overlay = frame.copy()
        cv.rectangle(hud_overlay, (0, hud_y), (frame.shape[1], frame.shape[0]), (25, 25, 25), -1)
        frame = cv.addWeighted(frame, 0.30, hud_overlay, 0.70, 0)
        cv.line(frame, (0, hud_y), (frame.shape[1], hud_y), (60, 60, 60), 1)

        if not tracking:
            status_text = "MODE: LOST | Bring hand into view to draw"
            text_color = (0, 0, 255)
        elif self.status_message_frames > 0:
            status_text = f"ACTION: {self.status_message}"
            text_color = (0, 255, 255)
            self.status_message_frames -= 1
        else:
            status_text = f"MODE: {gesture.value} | TOOL: {self.shape.name} | COLOR: {self.color.name} | BRUSH: {self.brush_size}px"
            text_color = (240, 240, 240)

        cv.putText(frame, status_text, (15, frame.shape[0] - 12),
                   cv.FONT_HERSHEY_SIMPLEX, 0.48, text_color, 1, cv.LINE_AA)

        undo_status = f"UNDO: {'YES' if self.can_undo else 'NO'} | REDO: {'YES' if self.can_redo else 'NO'}"
        cv.putText(frame, undo_status, (max(15, frame.shape[1] - 230), frame.shape[0] - 12),
                   cv.FONT_HERSHEY_SIMPLEX, 0.45, (170, 170, 170), 1, cv.LINE_AA)

        return frame
    
    def update_and_draw(self, frame, data = {}):
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

def replay(fname):
    print("replaying", fname)

    cap = cv.VideoCapture(fname)
    # Use whatever width and height possible
    frame_width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

    canvas = Canvas(frame_height, frame_width)

    if (not cap.isOpened()):
        print("Error opening video file")
        return

    detector = HandDetector()
    while cap.isOpened() and (cv.waitKey(0) & 0xFF != ord('q')):
        ret, img = cap.read()

        # replay is completed when the video capture no longer has any frames to read.
        if ret:

            gesture_metadata = detector.get_gesture_metadata(img)

            img = canvas.update_and_draw(img, gesture_metadata)
            detector.draw_landmarks(img)

            cv.imshow('Camera', img)
        else:
            break

    cap.release()
    cv.destroyAllWindows()

    print("replay complete", fname)


def main():
    canvas = Canvas(100, 200)
    line = Line("BLUE", (1, 1))
    line.points.append((10, 5))
    print(line)


if __name__ == '__main__':
    import sys
    import os
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        replay(sys.argv[1])
    else:
        main()
