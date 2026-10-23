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
