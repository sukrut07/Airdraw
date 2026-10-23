"""AirDraw's application lifecycle, onboarding, webcam loop, and export actions."""

import os
import sys
from datetime import datetime
from typing import Any, Optional

import cv2 as cv
import numpy as np

from canvas import Canvas
from hands import HandDetector
from onboarding import AppState, CameraErrorScreen, OnboardingScreen
from persistence import (
    DEFAULT_CONFIG_PATH,
    export_png,
    has_completed_onboarding,
    save_project,
    set_onboarding_completed,
)


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
    elif key == ord("t"):
        canvas.reopen_tutorial = True
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


class AirDrawApp:
    """
    Main application orchestrator managing the AirDraw lifecycle:
    - Pre-camera onboarding flow (Start Drawing / Skip Tutorial)
    - Single shared camera & MediaPipe initialization path
    - Live drawing loop with gesture updates and canvas rendering
    - Camera error recovery screen (Retry / Back to Guide / Exit)
    - Clean resource management and reopening of onboarding tutorial
    """

    def __init__(
        self,
        camera_index: int = 0,
        config_path: str = DEFAULT_CONFIG_PATH,
        force_onboarding: bool = False,
        window_name: str = "AirDraw",
    ):
        self.camera_index = camera_index
        self.config_path = config_path
        self.window_name = window_name
        self.force_onboarding = force_onboarding

        self.state: AppState = AppState.ONBOARDING
        self.capture: Optional[cv.VideoCapture] = None
        self.detector: Optional[HandDetector] = None
        self.canvas: Optional[Canvas] = None
        self.error_message: str = ""
        self.window_width: int = 960
        self.window_height: int = 600

        # Sub-screens
        self.onboarding = OnboardingScreen(
            on_start=self.start_drawing,
            on_skip=self.skip_tutorial,
            on_exit=self.exit_app,
        )
        self.camera_error_screen = CameraErrorScreen(
            on_retry=self.retry_camera,
            on_back_to_guide=self.reopen_tutorial,
            on_exit=self.exit_app,
        )

        # Decide initial state: show onboarding on first launch or if explicitly requested
        if not self.force_onboarding and has_completed_onboarding(self.config_path):
            self.state = AppState.INITIALIZING_CAMERA
        else:
            self.state = AppState.ONBOARDING

    def _mouse_callback(self, event: int, x: int, y: int, flags: int, param: Any) -> None:
        """Route OpenCV mouse events based on current application state."""
        if self.state == AppState.ONBOARDING:
            self.onboarding.handle_mouse(event, x, y, flags, param)
        elif self.state == AppState.CAMERA_ERROR:
            self.camera_error_screen.handle_mouse(event, x, y, flags, param)

    def start_drawing(self) -> None:
        """Triggered from Onboarding 'Start Drawing'."""
        if self.state != AppState.ONBOARDING:
            return  # Rapid-click and state guard
        set_onboarding_completed(True, self.config_path)
        self.initialize_camera()

    def skip_tutorial(self) -> None:
        """Triggered from Onboarding 'Skip Tutorial'."""
        if self.state != AppState.ONBOARDING:
            return  # Rapid-click and state guard
        set_onboarding_completed(True, self.config_path)
        self.initialize_camera()

    def retry_camera(self) -> None:
        """Retry camera initialization from the error screen."""
        if self.state != AppState.CAMERA_ERROR:
            return
        self.initialize_camera()

    def reopen_tutorial(self) -> None:
        """Pause drawing, cleanly release camera/MediaPipe, and return to onboarding."""
        self.stop_camera()
        self.state = AppState.ONBOARDING

    def exit_app(self) -> None:
        """Signal clean exit."""
        self.state = AppState.EXITING

    def stop_camera(self) -> None:
        """Safely release camera and MediaPipe resources without leaking."""
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception:
                pass
            self.capture = None

        if self.detector is not None:
            try:
                self.detector.close()
            except Exception:
                pass
            self.detector = None

    def initialize_camera(self) -> bool:
        """
        Single, authoritative camera & MediaPipe initialization path.
        Used by Start Drawing, Skip Tutorial, and Error Retry.
        Guarantees no duplicate camera captures are opened.
        """
        self.stop_camera()
        self.state = AppState.INITIALIZING_CAMERA

        # Attempt to open webcam
        try:
            capture = cv.VideoCapture(self.camera_index)
            if not capture.isOpened():
                capture.release()
                self.error_message = (
                    f"Could not open webcam (index {self.camera_index}). "
                    "Check connection and camera permissions."
                )
                self.camera_error_screen.set_error_message(self.error_message)
                self.state = AppState.CAMERA_ERROR
                return False

            # Test reading initial frame
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.release()
                self.error_message = "Failed to capture initial frame from webcam."
                self.camera_error_screen.set_error_message(self.error_message)
                self.state = AppState.CAMERA_ERROR
                return False

            self.capture = capture

            # Attempt to initialize HandDetector (MediaPipe)
            try:
                self.detector = HandDetector()
            except Exception as e:
                self.stop_camera()
                self.error_message = f"MediaPipe initialization error: {e}"
                self.camera_error_screen.set_error_message(self.error_message)
                self.state = AppState.CAMERA_ERROR
                return False

            # Initialize or update canvas resolution based on camera frame
            h, w = frame.shape[:2]
            self.window_width = w
            self.window_height = h
            if self.canvas is None:
                self.canvas = Canvas(height=h, width=w)
                print(f"AirDraw ready ({w} x {h})")
                print("Raise index finger to hover/select tools. Press [H] for guide, [T] for tutorial.")
            else:
                self.canvas.height = h
                self.canvas.width = w
                self.canvas.rows = h
                self.canvas.columns = w

            self.state = AppState.DRAWING
            return True

        except Exception as e:
            self.stop_camera()
            self.error_message = f"Unexpected camera initialization error: {e}"
            self.camera_error_screen.set_error_message(self.error_message)
            self.state = AppState.CAMERA_ERROR
            return False

    def run(self) -> None:
        """Main event loop managing state transitions and UI rendering."""
        cv.namedWindow(self.window_name, cv.WINDOW_NORMAL)
        cv.setMouseCallback(self.window_name, self._mouse_callback)

        try:
            while self.state != AppState.EXITING:
                if self.state == AppState.ONBOARDING:
                    frame = self.onboarding.render(self.window_width, self.window_height)
                    cv.imshow(self.window_name, frame)
                    key = cv.waitKey(25) & 0xFF
                    if key != 255:
                        self.onboarding.handle_key(key)

                elif self.state == AppState.INITIALIZING_CAMERA:
                    # Provide visual feedback while starting webcam
                    splash = np.full((self.window_height, self.window_width, 3), (22, 22, 26), dtype=np.uint8)
                    cv.putText(
                        splash,
                        "Starting camera & hand tracking...",
                        (self.window_width // 2 - 160, self.window_height // 2),
                        cv.FONT_HERSHEY_SIMPLEX,
                        0.60,
                        (255, 180, 50),
                        1,
                        cv.LINE_AA,
                    )
                    cv.imshow(self.window_name, splash)
                    cv.waitKey(1)
                    self.initialize_camera()

                elif self.state == AppState.CAMERA_ERROR:
                    frame = self.camera_error_screen.render(self.window_width, self.window_height, self.error_message)
                    cv.imshow(self.window_name, frame)
                    key = cv.waitKey(25) & 0xFF
                    if key != 255:
                        self.camera_error_screen.handle_key(key)

                elif self.state == AppState.DRAWING:
                    if self.capture is None or self.detector is None or self.canvas is None:
                        self.initialize_camera()
                        continue

                    ok, frame = self.capture.read()
                    if not ok or frame is None:
                        print("Warning: failed to read a frame from webcam.")
                        self.error_message = "Lost connection to webcam stream."
                        self.camera_error_screen.set_error_message(self.error_message)
                        self.state = AppState.CAMERA_ERROR
                        continue

                    frame = cv.flip(frame, 1)
                    metadata = self.detector.get_gesture_metadata(frame)
                    frame = self.canvas.update_and_draw(frame, metadata)
                    self.detector.draw_landmarks(frame)
                    cv.imshow(self.window_name, frame)

                    key = cv.waitKey(1) & 0xFF
                    if key == ord("t") or getattr(self.canvas, "reopen_tutorial", False):
                        if self.canvas:
                            self.canvas.reopen_tutorial = False
                        self.reopen_tutorial()
                    elif not handle_keypress(key, self.canvas):
                        self.state = AppState.EXITING

        finally:
            self.stop_camera()
            cv.destroyAllWindows()


def main(camera_index: int = 0, force_onboarding: Optional[bool] = None) -> None:
    """Run AirDraw with full lifecycle, onboarding, and webcam tracking."""
    args = sys.argv[1:]
    if force_onboarding is None:
        force_onboarding = ("--onboarding" in args or "--tutorial" in args)

    if "--help" in args or "-h" in args:
        print("AirDraw — Touchless Hand-Gesture Drawing Application")
        print("\nOptions:")
        print("  --onboarding, --tutorial   Force display of gesture onboarding tutorial")
        print("  --no-onboarding            Bypass onboarding directly into camera stream")
        print("  --camera <idx>             Specify webcam device index (default: 0)")
        print("  --help, -h                 Show this help message")
        return

    if "--no-onboarding" in args:
        force_onboarding = False
        set_onboarding_completed(True)

    if "--camera" in args:
        try:
            c_idx = args.index("--camera")
            camera_index = int(args[c_idx + 1])
        except (ValueError, IndexError):
            print("Warning: invalid --camera index, using default 0")

    app = AirDrawApp(camera_index=camera_index, force_onboarding=force_onboarding)
    app.run()


if __name__ == "__main__":
    main()

