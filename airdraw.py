"""AirDraw's webcam loop, keyboard shortcuts, and drawing export actions."""

import os
from datetime import datetime

import cv2 as cv

from canvas import Canvas
from hands import HandDetector
from persistence import export_png, save_project


def _timestamp() -> str:
    """Return a filesystem-friendly timestamp that avoids same-second collisions."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def save_snapshot(canvas: Canvas) -> None:
    """Save an editable project and a clean PNG, reporting partial failures honestly."""
    timestamp = _timestamp()
    project_path = f"projects/airdraw_{timestamp}.json"
    image_path = f"exports/airdraw_{timestamp}.png"

    project_saved = save_project(canvas, project_path)
    image_exported = export_png(canvas, image_path, transparent=False)

    if project_saved and image_exported:
        canvas.set_status(f"Saved project + {os.path.basename(image_path)}")
    elif project_saved:
        canvas.set_status("Project saved; PNG export failed")
    elif image_exported:
        canvas.set_status("PNG exported; project save failed")
    else:
        canvas.set_status("Save failed - check terminal output")


def export_transparent_snapshot(canvas: Canvas) -> None:
    """Export artwork only with transparent pixels outside the drawing."""
    image_path = f"exports/airdraw_trans_{_timestamp()}.png"
    if export_png(canvas, image_path, transparent=True):
        canvas.set_status(f"Transparent PNG exported: {os.path.basename(image_path)}")
    else:
        canvas.set_status("Transparent PNG export failed - check terminal output")


def handle_keypress(key: int, canvas: Canvas) -> bool:
    """Handle one OpenCV key code. Return False when the app should quit."""
    if key in (ord("h"), ord("?")):
        canvas.toggle_help()
    elif key == 27 and canvas.show_help:
        canvas.show_help = False
    elif key in (ord("q"), 27):
        return False
    elif key == ord("b"):
        canvas.switch_background()
        background = "Dark whiteboard" if canvas.blackout_background else "Camera background"
        canvas.set_status(background)
    elif key in (ord("z"), 26):
        canvas.undo()
    elif key in (ord("y"), 25):
        canvas.redo()
    elif key == ord("["):
        canvas.set_brush_size(canvas.brush_size - 2)
    elif key == ord("]"):
        canvas.set_brush_size(canvas.brush_size + 2)
    elif key in (ord("s"), 19):
        save_snapshot(canvas)
    elif key == ord("e"):
        export_transparent_snapshot(canvas)

    return True


def replay(filename: str) -> None:
    """Replay a video through the hand-tracking canvas until it ends or Q is pressed."""
    capture = cv.VideoCapture(filename)
    if not capture.isOpened():
        capture.release()
        print(f"Error: could not open video file: {filename}")
        return

    detector = None
    canvas = None
    try:
        detector = HandDetector()
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                break

            if canvas is None:
                height, width = frame.shape[:2]
                canvas = Canvas(height=height, width=width)

            metadata = detector.get_gesture_metadata(frame)
            frame = canvas.update_and_draw(frame, metadata)
            detector.draw_landmarks(frame)
            cv.imshow("AirDraw - Replay", frame)

            if cv.waitKey(30) & 0xFF in (ord("q"), 27):
                break
    finally:
        capture.release()
        if detector is not None:
            detector.close()
        cv.destroyAllWindows()

    print(f"Replay finished: {filename}")


def main() -> None:
    """Run AirDraw with the default webcam and always release acquired resources."""
    capture = cv.VideoCapture(0)
    if not capture.isOpened():
        capture.release()
        print("Error: could not open webcam. Check the connection and camera permissions.")
        return

    detector = None
    canvas = None
    try:
        detector = HandDetector()
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                print("Warning: failed to read a frame from the webcam.")
                break

            frame = cv.flip(frame, 1)
            if canvas is None:
                height, width = frame.shape[:2]
                canvas = Canvas(height=height, width=width)
                print(f"AirDraw ready ({width} x {height})")
                print("Raise your index finger to select tools. Press H for gestures and shortcuts.")

            metadata = detector.get_gesture_metadata(frame)
            frame = canvas.update_and_draw(frame, metadata)
            detector.draw_landmarks(frame)
            cv.imshow("AirDraw", frame)

            key = cv.waitKey(1) & 0xFF
            if not handle_keypress(key, canvas):
                break
    finally:
        capture.release()
        if detector is not None:
            detector.close()
        cv.destroyAllWindows()


if __name__ == "__main__":
    main()
