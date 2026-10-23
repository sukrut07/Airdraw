"""
Unit tests for the DrawingHistory system and Command pattern implementations.
"""
import pytest
from canvas import Canvas, Line, Circle, Square, Color, Shape
from history import (
    DrawingHistory,
    AddLineCommand,
    AddCircleCommand,
    AddSquareCommand,
    EraseCommand,
    TranslateCommand,
    ClearCanvasCommand
)


def test_add_line_undo_redo():
    canvas = Canvas(height=480, width=640)
    history = DrawingHistory()

    line = Line(Color.BLUE, (50, 50))
    line.points.append((55, 55))
    canvas.lines[line.get_origin()] = line

    history.push(AddLineCommand(line))
    assert len(canvas.lines) == 1
    assert history.can_undo is True
    assert history.can_redo is False

    # Undo
    assert history.undo(canvas) is True
    assert len(canvas.lines) == 0
    assert history.can_undo is False
    assert history.can_redo is True

    # Redo
    assert history.redo(canvas) is True
    assert len(canvas.lines) == 1
    assert history.can_undo is True
    assert history.can_redo is False


def test_add_circle_and_square_undo_redo():
    canvas = Canvas(height=480, width=640)
    history = DrawingHistory()

    circle = Circle((100, 100), 20, Color.RED)
    canvas.circles.append(circle)
    history.push(AddCircleCommand(circle))

    square = Square((200, 200), (250, 250), Color.GREEN)
    canvas.squares.append(square)
    history.push(AddSquareCommand(square))

    assert len(canvas.circles) == 1
    assert len(canvas.squares) == 1

    # Undo square
    assert history.undo(canvas) is True
    assert len(canvas.squares) == 0
    assert len(canvas.circles) == 1

    # Undo circle
    assert history.undo(canvas) is True
    assert len(canvas.circles) == 0

    # Redo circle
    assert history.redo(canvas) is True
    assert len(canvas.circles) == 1
    assert len(canvas.squares) == 0

    # Redo square
    assert history.redo(canvas) is True
    assert len(canvas.squares) == 1


def test_erase_command_undo_redo():
    canvas = Canvas(height=480, width=640)
    history = DrawingHistory()

    line = Line(Color.BLUE, (50, 50))
    canvas.lines[line.get_origin()] = line

    circle = Circle((100, 100), 20, Color.RED)
    canvas.circles.append(circle)

    # Perform erase
    canvas.lines.clear()
    canvas.circles.remove(circle)

    erase_cmd = EraseCommand(removed_lines=[line], removed_circles=[circle], removed_squares=[])
    history.push(erase_cmd)

    assert len(canvas.lines) == 0
    assert len(canvas.circles) == 0

    # Undo erase (restore items)
    assert history.undo(canvas) is True
    assert len(canvas.lines) == 1
    assert len(canvas.circles) == 1

    # Redo erase
    assert history.redo(canvas) is True
    assert len(canvas.lines) == 0
    assert len(canvas.circles) == 0


def test_clear_canvas_command_undo_redo():
    canvas = Canvas(height=480, width=640)
    history = DrawingHistory()

    line = Line(Color.BLUE, (50, 50))
    canvas.lines[line.get_origin()] = line
    circle = Circle((100, 100), 20, Color.RED)
    canvas.circles.append(circle)

    # Save previous state and clear
    clear_cmd = ClearCanvasCommand(saved_lines=canvas.lines, saved_circles=canvas.circles, saved_squares=canvas.squares)
    canvas.lines.clear()
    canvas.circles.clear()
    history.push(clear_cmd)

    assert len(canvas.lines) == 0
    assert len(canvas.circles) == 0

    # Undo clear
    assert history.undo(canvas) is True
    assert len(canvas.lines) == 1
    assert len(canvas.circles) == 1

    # Redo clear
    assert history.redo(canvas) is True
    assert len(canvas.lines) == 0
    assert len(canvas.circles) == 0


def test_redo_invalidated_by_new_action():
    canvas = Canvas(height=480, width=640)
    history = DrawingHistory()

    c1 = Circle((10, 10), 5, Color.BLUE)
    canvas.circles.append(c1)
    history.push(AddCircleCommand(c1))

    # Undo
    history.undo(canvas)
    assert history.can_redo is True

    # New action should clear redo stack
    c2 = Circle((20, 20), 10, Color.RED)
    canvas.circles.append(c2)
    history.push(AddCircleCommand(c2))

    assert history.can_redo is False
    assert history.redo(canvas) is False


def test_empty_history_safety():
    canvas = Canvas(height=480, width=640)
    history = DrawingHistory()

    assert history.undo(canvas) is False
    assert history.redo(canvas) is False
    assert history.can_undo is False
    assert history.can_redo is False


def test_max_history_limit():
    canvas = Canvas(height=480, width=640)
    history = DrawingHistory(max_history=3)

    for i in range(5):
        c = Circle((i * 10, i * 10), 5, Color.BLUE)
        history.push(AddCircleCommand(c))

    assert len(history.undo_stack) == 3
