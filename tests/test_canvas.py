"""
Unit tests for Canvas geometry, shape representation, and canvas operations.
"""
import pytest
import numpy as np
from canvas import Canvas, Line, Circle, Square, Color, Shape
from hands import Gesture


def test_canvas_initialization():
    canvas = Canvas(height=480, width=640)
    assert canvas.height == 480
    assert canvas.width == 640
    assert canvas.rows == 480
    assert canvas.columns == 640
    assert canvas.color == Color.BLUE
    assert canvas.shape == Shape.LINE
    assert len(canvas.lines) == 0
    assert len(canvas.circles) == 0
    assert len(canvas.squares) == 0


def test_line_creation_and_drawing():
    canvas = Canvas(height=480, width=640)
    canvas.color = Color.GREEN

    # Simulate drawing gesture
    canvas.push_point((100, 150))
    assert len(canvas.lines) == 1
    active_line = list(canvas.lines.values())[0] if isinstance(canvas.lines, dict) else canvas.lines[0]
    assert active_line.color == Color.GREEN
    assert active_line.points == [(100, 150)]

    canvas.push_point((102, 152))
    assert active_line.points == [(100, 150), (102, 152)]

    canvas.end_drawing()
    assert not active_line.active


def test_circle_creation_and_resizing():
    canvas = Canvas(height=480, width=640)
    canvas.color = Color.RED
    canvas.shape = Shape.CIRCLE

    canvas.update_circle((200, 200))
    assert len(canvas.circles) == 1
    circle = canvas.circles[0]
    assert circle.origin == (200, 200)

    # Grow circle to new point
    canvas.update_circle((200, 250))
    assert circle.radius == pytest.approx(50, abs=1)

    canvas.end_drawing()
    assert not circle.active


def test_square_creation_and_bounds():
    canvas = Canvas(height=480, width=640)
    canvas.color = Color.BLUE
    canvas.shape = Shape.SQUARE

    canvas.update_square((100, 100))
    assert len(canvas.squares) == 1
    square = canvas.squares[0]

    canvas.update_square((200, 300))
    top, left, bottom, right = square.get_coords()
    assert top == 100
    assert left == 100
    assert bottom == 200
    assert right == 300

    assert square.get_height() == 100
    assert square.get_width() == 200


def test_square_overlaps_circle():
    # Square from (100, 100) to (200, 200)
    square = Square(anchor=(100, 100), opposite=(200, 200), color=Color.BLUE)

    # Point directly on top edge
    assert square.overlaps_circle((100, 150), 5) is True

    # Point outside and far away
    assert square.overlaps_circle((400, 400), 10) is False

    # Point inside the box
    assert square.overlaps_circle((150, 150), 60) is True


def test_erase_mode():
    canvas = Canvas(height=480, width=640)

    # Add a line at (100, 100) to (105, 105)
    canvas.push_point((100, 100))
    canvas.push_point((105, 105))
    canvas.end_drawing()

    # Add circle at (300, 300) with radius 20
    circle = Circle((300, 300), 20, Color.BLUE)
    canvas.circles.append(circle)

    # Erase near the line
    canvas.erase_mode((102, 102), radius=15)
    lines_count = len(canvas.lines)
    assert lines_count == 0
    # Circle should still exist
    assert len(canvas.circles) == 1

    # Erase near circle
    canvas.erase_mode((300, 320), radius=10)
    assert len(canvas.circles) == 0


def test_translate_mode_no_crash():
    canvas = Canvas(height=480, width=640)
    canvas.push_point((100, 100))
    canvas.push_point((105, 105))
    canvas.end_drawing()

    circle = Circle((200, 200), 15, Color.BLUE)
    canvas.circles.append(circle)

    # Shift with (0, 0) should be a safe no-op
    canvas.translate_mode((100, 100), radius=30, shift=(0, 0))

    # Shift with positive delta
    canvas.translate_mode((100, 100), radius=30, shift=(10, 20))

    # Test shift that would push past canvas boundaries
    canvas.translate_mode((110, 120), radius=30, shift=(1000, 1000))


def test_clear_dwell_protection():
    canvas = Canvas(height=480, width=640)
    canvas.push_point((100, 100))
    canvas.end_drawing()
    assert len(canvas.lines) == 1

    # Clear button coordinates from get_buttons_coords
    coords = canvas.get_buttons_coords((480, 640, 3))
    clear_btn = coords[0]
    # Center of clear button in (row, col) format
    btn_r = (clear_btn[2][1] + clear_btn[3][1]) // 2
    btn_c = (clear_btn[2][0] + clear_btn[3][0]) // 2

    # Simulate 5 frames of hover over Clear All (less than 25 threshold)
    hover_data = {
        'tracking': True,
        'gesture': Gesture.HOVER,
        'idx_fing_tip': (btn_r, btn_c),
        'origin': (btn_r, btn_c)
    }
    for _ in range(5):
        canvas.update_state((480, 640, 3), hover_data)

    # Artwork should NOT be cleared yet!
    assert len(canvas.lines) == 1
    assert canvas.clear_hovering is True
    assert canvas.clear_dwell_frames == 5

    # Move away from button
    away_data = {
        'tracking': True,
        'gesture': Gesture.HOVER,
        'idx_fing_tip': (300, 300),
        'origin': (300, 300)
    }
    canvas.update_state((480, 640, 3), away_data)
    assert canvas.clear_dwell_frames == 0
    assert canvas.clear_hovering is False
    assert len(canvas.lines) == 1

    # Now hover for full dwell duration (25 frames)
    for _ in range(25):
        canvas.update_state((480, 640, 3), hover_data)

    # Artwork should NOW be cleared
    assert len(canvas.lines) == 0


def test_missing_tracking_safety():
    canvas = Canvas(height=480, width=640)
    canvas.push_point((100, 100))
    assert canvas.currLine.active is True

    # Tracking lost
    lost_data = {
        'tracking': False,
        'gesture': Gesture.NONE,
        'origin': None
    }
    canvas.update_state((480, 640, 3), lost_data)
    assert canvas.currLine.active is False

    # Rendering during tracking loss should not crash
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    rendered = canvas.draw_canvas(frame, lost_data)
    assert rendered is not None


def test_canvas_undo_redo_integration():
    canvas = Canvas(height=480, width=640)

    # Draw a line
    canvas.push_point((100, 100))
    canvas.push_point((110, 110))
    canvas.end_drawing()
    assert len(canvas.lines) == 1
    assert canvas.can_undo is True

    # Undo removes the line
    assert canvas.undo() is True
    assert len(canvas.lines) == 0
    assert canvas.can_redo is True

    # Redo restores the line
    assert canvas.redo() is True
    assert len(canvas.lines) == 1


def test_canvas_clear_undo():
    canvas = Canvas(height=480, width=640)
    canvas.push_point((100, 100))
    canvas.push_point((110, 110))
    canvas.end_drawing()

    circle = Circle((200, 200), 20, Color.RED)
    canvas.circles.append(circle)

    coords = canvas.get_buttons_coords((480, 640, 3))
    clear_btn = coords[0]
    btn_r = (clear_btn[2][1] + clear_btn[3][1]) // 2
    btn_c = (clear_btn[2][0] + clear_btn[3][0]) // 2

    hover_data = {
        'tracking': True,
        'gesture': Gesture.HOVER,
        'idx_fing_tip': (btn_r, btn_c),
        'origin': (btn_r, btn_c)
    }

    # Dwell to clear
    for _ in range(25):
        canvas.update_state((480, 640, 3), hover_data)

    assert len(canvas.lines) == 0
    assert len(canvas.circles) == 0

    # Undo the clear operation!
    assert canvas.undo() is True
    assert len(canvas.lines) == 1
    assert len(canvas.circles) == 1


def test_canvas_brush_size():
    canvas = Canvas(height=480, width=640)
    canvas.set_brush_size(14)
    assert canvas.brush_size == 14

    canvas.push_point((50, 50))
    canvas.push_point((60, 60))
    canvas.end_drawing()

    line = list(canvas.lines.values())[0] if isinstance(canvas.lines, dict) else canvas.lines[0]
    assert line.thickness == 14
