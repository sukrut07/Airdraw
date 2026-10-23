"""
Project persistence and export utilities for AirDraw.
Provides JSON project save/load and clean PNG/transparent PNG drawing export.
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
import numpy as np
import cv2 as cv

from canvas import Color, Line, Circle, Square

PROJECT_FORMAT_VERSION = "1.0"


def serialize_canvas(canvas: Any) -> Dict[str, Any]:
    """Serializes canvas drawing objects into structured dictionary."""
    lines_data = []
    lines_source = canvas.lines.values() if isinstance(canvas.lines, dict) else canvas.lines
    for line in lines_source:
        lines_data.append({
            "color": line.color.name,
            "thickness": getattr(line, "thickness", 5),
            "points": [list(pt) for pt in line.points],
        })

    circles_data = []
    for circle in canvas.circles:
        circles_data.append({
            "color": circle.color.name,
            "origin": list(circle.origin),
            "radius": int(circle.radius),
            "thickness": getattr(circle, "thickness", 3),
        })

    squares_data = []
    for square in canvas.squares:
        squares_data.append({
            "color": square.color.name,
            "anchor": list(square.anchor),
            "opposite": list(square.opposite),
            "thickness": getattr(square, "thickness", 5),
        })

    return {
        "version": PROJECT_FORMAT_VERSION,
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "generator": "AirDraw",
        },
        "canvas": {
            "height": canvas.height,
            "width": canvas.width,
            "blackout_background": getattr(canvas, "blackout_background", False),
        },
        "objects": {
            "lines": lines_data,
            "circles": circles_data,
            "squares": squares_data,
        },
    }


def save_project(canvas: Any, filepath: str) -> bool:
    """Saves canvas drawing data to a JSON project file."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        data = serialize_canvas(canvas)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving project to {filepath}: {e}")
        return False


def load_project(canvas: Any, filepath: str) -> bool:
    """Loads and validates a JSON project file into the canvas."""
    try:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return False

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "objects" not in data:
            print(f"Invalid AirDraw project format: {filepath}")
            return False

        objects = data.get("objects", {})
        loaded_lines = {} if isinstance(canvas.lines, dict) else []
        loaded_circles = []
        loaded_squares = []

        # Load lines
        for item in objects.get("lines", []):
            color_name = item.get("color", "BLUE")
            color = Color[color_name] if color_name in Color.__members__ else Color.BLUE
            thickness = int(item.get("thickness", 5))
            raw_points = item.get("points", [])
            points = [(int(p[0]), int(p[1])) for p in raw_points if len(p) == 2]
            if points:
                line = Line(color, points[0], thickness=thickness)
                line.points = points
                line.active = False
                if isinstance(loaded_lines, dict):
                    loaded_lines[points[0]] = line
                else:
                    loaded_lines.append(line)

        # Load circles
        for item in objects.get("circles", []):
            color_name = item.get("color", "RED")
            color = Color[color_name] if color_name in Color.__members__ else Color.RED
            origin = tuple(item.get("origin", (100, 100)))
            radius = int(item.get("radius", 20))
            thickness = int(item.get("thickness", 3))
            circle = Circle(origin, radius, color, thickness=thickness)
            circle.active = False
            loaded_circles.append(circle)

        # Load squares
        for item in objects.get("squares", []):
            color_name = item.get("color", "GREEN")
            color = Color[color_name] if color_name in Color.__members__ else Color.GREEN
            anchor = tuple(item.get("anchor", (100, 100)))
            opposite = tuple(item.get("opposite", (200, 200)))
            thickness = int(item.get("thickness", 5))
            square = Square(anchor, opposite, color, thickness=thickness)
            square.active = False
            loaded_squares.append(square)

        # Apply to canvas
        canvas.end_drawing()
        canvas.lines = loaded_lines
        canvas.circles = loaded_circles
        canvas.squares = loaded_squares
        canvas.history.clear()
        canvas.set_status("Project Loaded")
        return True

    except Exception as e:
        print(f"Error loading project from {filepath}: {e}")
        return False


def render_drawing_layer(canvas: Any, transparent: bool = False, background_color=(0, 0, 0)) -> np.ndarray:
    """
    Renders pure artwork (lines, circles, squares) without camera feeds,
    tracking landmarks, or HUD buttons.
    """
    height = canvas.height
    width = canvas.width

    if transparent:
        # 4-channel BGRA image initialized with transparent zeros
        img = np.zeros((height, width, 4), dtype=np.uint8)
        # Render lines
        lines_source = canvas.lines.values() if isinstance(canvas.lines, dict) else canvas.lines
        for line in lines_source:
            b, g, r = line.color.value
            color_bgra = (b, g, r, 255)
            thick = getattr(line, "thickness", 5)
            for i, point in enumerate(line.points):
                if i == 0:
                    continue
                prev_r, prev_c = line.points[i - 1]
                cur_r, cur_c = point
                cv.line(img, (prev_c, prev_r), (cur_c, cur_r), color_bgra, thick)

        # Render circles
        for circle in canvas.circles:
            orig_row, orig_col = circle.origin
            b, g, r = circle.color.value
            color_bgra = (b, g, r, 255)
            thick = getattr(circle, "thickness", 3)
            cv.circle(img, (orig_col, orig_row), circle.radius, color_bgra, thick)

        # Render squares
        for square in canvas.squares:
            topRow, leftCol, bottomRow, rightCol = square.get_coords()
            b, g, r = square.color.value
            color_bgra = (b, g, r, 255)
            thick = getattr(square, "thickness", 5)
            cv.rectangle(img, (leftCol, topRow), (rightCol, bottomRow), color_bgra, thick)

        return img

    else:
        # 3-channel BGR image initialized with background_color
        img = np.full((height, width, 3), background_color, dtype=np.uint8)
        # Render lines
        lines_source = canvas.lines.values() if isinstance(canvas.lines, dict) else canvas.lines
        for line in lines_source:
            thick = getattr(line, "thickness", 5)
            for i, point in enumerate(line.points):
                if i == 0:
                    continue
                prev_r, prev_c = line.points[i - 1]
                cur_r, cur_c = point
                cv.line(img, (prev_c, prev_r), (cur_c, cur_r), line.color.value, thick)

        # Render circles
        for circle in canvas.circles:
            orig_row, orig_col = circle.origin
            thick = getattr(circle, "thickness", 3)
            cv.circle(img, (orig_col, orig_row), circle.radius, circle.color.value, thick)

        # Render squares
        for square in canvas.squares:
            topRow, leftCol, bottomRow, rightCol = square.get_coords()
            thick = getattr(square, "thickness", 5)
            cv.rectangle(img, (leftCol, topRow), (rightCol, bottomRow), square.color.value, thick)

        return img


def export_png(canvas: Any, filepath: str, transparent: bool = False, background_color=(0, 0, 0)) -> bool:
    """Exports clean artwork to a PNG file (supports transparent alpha channel)."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        img = render_drawing_layer(canvas, transparent=transparent, background_color=background_color)
        success = cv.imwrite(filepath, img)
        if success:
            canvas.set_status(f"Exported to {os.path.basename(filepath)}")
        return bool(success)
    except Exception as e:
        print(f"Error exporting image to {filepath}: {e}")
        return False
