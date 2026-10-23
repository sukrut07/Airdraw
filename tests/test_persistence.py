"""
Unit tests for persistence, project serialization, loading, and PNG export.
"""
import os
import tempfile
import pytest
import numpy as np
import cv2 as cv

from canvas import Canvas, Line, Circle, Square, Color
from persistence import (
    serialize_canvas,
    save_project,
    load_project,
    render_drawing_layer,
    export_png,
)


def test_serialize_and_save_load_project():
    canvas = Canvas(height=480, width=640)

    # Add line
    line = Line(Color.GREEN, (100, 100), thickness=8)
    line.points.append((120, 140))
    canvas.lines[line.get_origin()] = line

    # Add circle
    circle = Circle((200, 200), 25, Color.BLUE, thickness=4)
    canvas.circles.append(circle)

    # Add square
    square = Square((300, 300), (350, 380), Color.RED, thickness=6)
    canvas.squares.append(square)

    with tempfile.TemporaryDirectory() as tmpdir:
        proj_path = os.path.join(tmpdir, "test_proj.json")

        # Save project
        assert save_project(canvas, proj_path) is True
        assert os.path.exists(proj_path)

        # Load into fresh canvas
        new_canvas = Canvas(height=480, width=640)
        assert load_project(new_canvas, proj_path) is True

        assert len(new_canvas.lines) == 1
        loaded_line = list(new_canvas.lines.values())[0] if isinstance(new_canvas.lines, dict) else new_canvas.lines[0]
        assert loaded_line.color == Color.GREEN
        assert loaded_line.thickness == 8
        assert loaded_line.points == [(100, 100), (120, 140)]

        assert len(new_canvas.circles) == 1
        assert new_canvas.circles[0].origin == (200, 200)
        assert new_canvas.circles[0].radius == 25
        assert new_canvas.circles[0].color == Color.BLUE
        assert new_canvas.circles[0].thickness == 4

        assert len(new_canvas.squares) == 1
        assert new_canvas.squares[0].anchor == (300, 300)
        assert new_canvas.squares[0].opposite == (350, 380)
        assert new_canvas.squares[0].color == Color.RED
        assert new_canvas.squares[0].thickness == 6


def test_load_malformed_project_fails_safely():
    canvas = Canvas(height=480, width=640)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Non-existent file
        assert load_project(canvas, os.path.join(tmpdir, "missing.json")) is False

        # Corrupted JSON
        corrupted_path = os.path.join(tmpdir, "bad.json")
        with open(corrupted_path, "w") as f:
            f.write("{ invalid json content ...")
        assert load_project(canvas, corrupted_path) is False


def test_render_drawing_layer_channels_and_dimensions():
    canvas = Canvas(height=400, width=600)
    line = Line(Color.RED, (50, 50), thickness=5)
    line.points.append((70, 70))
    canvas.lines[line.get_origin()] = line

    # Opaque layer -> 3 channels (BGR)
    opaque = render_drawing_layer(canvas, transparent=False)
    assert opaque.shape == (400, 600, 3)

    # Transparent layer -> 4 channels (BGRA)
    transparent = render_drawing_layer(canvas, transparent=True)
    assert transparent.shape == (400, 600, 4)


def test_export_png_files():
    canvas = Canvas(height=300, width=400)
    circle = Circle((150, 200), 30, Color.BLUE, thickness=4)
    canvas.circles.append(circle)

    with tempfile.TemporaryDirectory() as tmpdir:
        opaque_path = os.path.join(tmpdir, "export.png")
        assert export_png(canvas, opaque_path, transparent=False) is True
        assert os.path.exists(opaque_path)

        read_opaque = cv.imread(opaque_path)
        assert read_opaque is not None
        assert read_opaque.shape == (300, 400, 3)

        transparent_path = os.path.join(tmpdir, "export_trans.png")
        assert export_png(canvas, transparent_path, transparent=True) is True
        assert os.path.exists(transparent_path)

        read_trans = cv.imread(transparent_path, cv.IMREAD_UNCHANGED)
        assert read_trans is not None
        assert read_trans.shape == (300, 400, 4)
