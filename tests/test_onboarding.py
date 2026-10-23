"""
Automated unit tests for AirDraw's first-launch onboarding, lifecycle, and camera error handling.
Validates pre-camera onboarding, gesture accuracy, shared camera initialization, and error states.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from airdraw import AirDrawApp, handle_keypress
from canvas import Canvas
from hands import Gesture
from onboarding import (
    AppState,
    CameraErrorScreen,
    GESTURE_DEFINITIONS,
    GESTURE_MAP,
    ONBOARDING_STEPS,
    OnboardingScreen,
)
from persistence import (
    has_completed_onboarding,
    load_app_config,
    save_app_config,
    set_onboarding_completed,
)


# ---------------------------------------------------------------------------
# Gesture Accuracy & Shared Source of Truth Tests
# ---------------------------------------------------------------------------

def test_gesture_definitions_match_hands_codebase():
    """Verify all gesture definitions align with Gesture enum from hands.py."""
    card_tags = {card.tag for card in GESTURE_DEFINITIONS}
    assert "NAVIGATE" in card_tags
    assert "DRAW" in card_tags
    assert "CREATE" in card_tags
    assert "ERASE" in card_tags
    assert "MOVE" in card_tags
    assert "CANVAS & KEYS" in card_tags

    # Hover card matches HOVER gesture
    hover_card = GESTURE_MAP["hover"]
    assert "1 Finger" in hover_card.pose or "Index" in hover_card.pose
    assert "toolbar" in hover_card.description.lower()

    # Draw card matches DRAW gesture
    draw_card = GESTURE_MAP["draw"]
    assert "2 Fingers" in draw_card.pose
    assert "strokes" in draw_card.description.lower()

    # Erase card matches ERASE gesture (fist / 3 fingers)
    erase_card = GESTURE_MAP["erase"]
    assert "Fist" in erase_card.pose and "3 Fingers" in erase_card.pose
    assert "wipes" in erase_card.description.lower() or "eraser" in erase_card.description.lower()

    # Translate card matches TRANSLATE gesture (open palm / horns)
    translate_card = GESTURE_MAP["translate"]
    assert "Open Palm" in translate_card.pose or "Horns" in translate_card.pose


def test_onboarding_steps_structure():
    """Verify multi-step onboarding tutorial contains valid card references."""
    assert len(ONBOARDING_STEPS) >= 3
    for step in ONBOARDING_STEPS:
        assert "title" in step
        assert "pill" in step
        assert "cards" in step
        for card_id in step["cards"]:
            assert card_id in GESTURE_MAP


# ---------------------------------------------------------------------------
# Onboarding Rendering & Responsiveness Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("width,height", [
    (640, 480),
    (800, 600),
    (960, 600),
    (1280, 720),
    (1920, 1080),
])
def test_onboarding_render_resolutions(width, height):
    """Verify onboarding renders correctly across standard and widescreen display resolutions."""
    screen = OnboardingScreen()
    img = screen.render(width=width, height=height)

    assert isinstance(img, np.ndarray)
    assert img.shape == (height, width, 3)
    assert img.dtype == np.uint8


def test_bottom_buttons_accessible_on_all_sizes():
    """Verify primary Start Drawing and secondary Skip Tutorial buttons are strictly on-screen."""
    test_sizes = [(640, 480), (800, 600), (960, 600), (1280, 720)]
    for w, h in test_sizes:
        screen = OnboardingScreen()
        screen.render(width=w, height=h)

        assert "start" in screen.buttons
        assert "skip" in screen.buttons

        start_x, start_y, start_w, start_h = screen.buttons["start"]
        skip_x, skip_y, skip_w, skip_h = screen.buttons["skip"]

        # Both buttons must be within window bounds
        assert 0 <= start_x and start_x + start_w <= w
        assert 0 <= start_y and start_y + start_h <= h
        assert 0 <= skip_x and skip_x + skip_w <= w
        assert 0 <= skip_y and skip_y + skip_h <= h

        # Skip Tutorial must be visibly positioned near the bottom
        assert skip_y >= h - 100


def test_onboarding_navigation_controls():
    """Test step progression, cycling, and direct tab selection."""
    screen = OnboardingScreen()
    assert screen.current_step == 0

    screen.next_step()
    assert screen.current_step == 1

    screen.next_step()
    assert screen.current_step == 2

    # Clamped at last step
    screen.next_step()
    assert screen.current_step == 2

    screen.prev_step()
    assert screen.current_step == 1

    screen.set_step(0)
    assert screen.current_step == 0

    # Bounds clamping
    screen.set_step(99)
    assert screen.current_step == screen.total_steps - 1
    screen.set_step(-5)
    assert screen.current_step == 0


def test_onboarding_mouse_interaction():
    """Test mouse hover and click callbacks on Start Drawing and Skip Tutorial."""
    start_called = []
    skip_called = []

    screen = OnboardingScreen(
        on_start=lambda: start_called.append(True),
        on_skip=lambda: skip_called.append(True),
    )
    screen.render(width=960, height=600)

    start_x, start_y, start_w, start_h = screen.buttons["start"]
    skip_x, skip_y, skip_w, skip_h = screen.buttons["skip"]

    # Hover over Start button
    screen.handle_mouse(0, start_x + 5, start_y + 5, 0)
    assert screen.hover_btn == "start"

    # Click Start button
    screen.handle_mouse(1, start_x + 5, start_y + 5, 0)  # cv.EVENT_LBUTTONDOWN = 1
    assert len(start_called) == 1

    # Hover and click Skip button
    screen.handle_mouse(0, skip_x + 5, skip_y + 5, 0)
    assert screen.hover_btn == "skip"
    screen.handle_mouse(1, skip_x + 5, skip_y + 5, 0)
    assert len(skip_called) == 1


def test_onboarding_keyboard_interaction():
    """Test keyboard shortcuts on OnboardingScreen."""
    start_called = []
    skip_called = []
    exit_called = []

    screen = OnboardingScreen(
        on_start=lambda: start_called.append(True),
        on_skip=lambda: skip_called.append(True),
        on_exit=lambda: exit_called.append(True),
    )

    # Enter or Space triggers Start
    screen.handle_key(13)  # Enter
    assert len(start_called) == 1
    screen.handle_key(32)  # Space
    assert len(start_called) == 2

    # 's' or Tab triggers Skip
    screen.handle_key(ord("s"))
    assert len(skip_called) == 1
    screen.handle_key(9)  # Tab
    assert len(skip_called) == 2

    # Step navigation keys
    screen.handle_key(ord("n"))
    assert screen.current_step == 1
    screen.handle_key(ord("p"))
    assert screen.current_step == 0

    # Quit triggers exit
    res = screen.handle_key(ord("q"))
    assert res is False
    assert len(exit_called) == 1


# ---------------------------------------------------------------------------
# Camera Error Screen Tests
# ---------------------------------------------------------------------------

def test_camera_error_screen_rendering():
    """Verify camera error recovery screen renders properly with buttons."""
    err_screen = CameraErrorScreen()
    img = err_screen.render(960, 600, error_message="Permission denied")
    assert img.shape == (600, 960, 3)

    assert "retry" in err_screen.buttons
    assert "guide" in err_screen.buttons
    assert "exit" in err_screen.buttons


def test_camera_error_screen_actions():
    """Test Retry, Guide, and Exit actions on error screen."""
    retry_called = []
    guide_called = []
    exit_called = []

    err_screen = CameraErrorScreen(
        on_retry=lambda: retry_called.append(True),
        on_back_to_guide=lambda: guide_called.append(True),
        on_exit=lambda: exit_called.append(True),
    )
    err_screen.render(960, 600)

    # Keys: 'r' for retry, 'b' for guide, 'q' for exit
    err_screen.handle_key(ord("r"))
    assert len(retry_called) == 1

    err_screen.handle_key(ord("b"))
    assert len(guide_called) == 1

    err_screen.handle_key(ord("q"))
    assert len(exit_called) == 1


# ---------------------------------------------------------------------------
# Application Lifecycle & Integration Tests
# ---------------------------------------------------------------------------

def test_onboarding_appears_before_camera_initialization(tmp_path):
    """Verify AirDrawApp starts in ONBOARDING state without opening camera."""
    cfg_file = str(tmp_path / "config.json")
    app = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)

    # Must be in ONBOARDING state
    assert app.state == AppState.ONBOARDING
    # Camera capture and hand detector must remain uninitialized (None)
    assert app.capture is None
    assert app.detector is None


def test_exit_during_onboarding_never_opens_camera(tmp_path):
    """Exiting during onboarding immediately transitions to EXITING without touching camera."""
    cfg_file = str(tmp_path / "config.json")
    app = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)

    app.exit_app()
    assert app.state == AppState.EXITING
    assert app.capture is None
    assert app.detector is None


@patch("airdraw.cv.VideoCapture")
@patch("airdraw.HandDetector")
def test_start_drawing_and_skip_tutorial_share_initialization_path(mock_detector, mock_cap_cls, tmp_path):
    """Verify Start Drawing and Skip Tutorial both invoke the identical initialize_camera method."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_cap_cls.return_value = mock_cap

    cfg_file = str(tmp_path / "config.json")

    # 1. Test Start Drawing
    app1 = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)
    assert app1.state == AppState.ONBOARDING

    app1.start_drawing()
    assert app1.state == AppState.DRAWING
    assert app1.capture is not None
    assert app1.detector is not None
    assert has_completed_onboarding(cfg_file)

    # 2. Test Skip Tutorial
    set_onboarding_completed(False, cfg_file)
    app2 = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)
    assert app2.state == AppState.ONBOARDING

    app2.skip_tutorial()
    assert app2.state == AppState.DRAWING
    assert app2.capture is not None
    assert app2.detector is not None
    assert has_completed_onboarding(cfg_file)


@patch("airdraw.cv.VideoCapture")
@patch("airdraw.HandDetector")
def test_skipping_onboarding_does_not_disable_drawing(mock_detector, mock_cap_cls, tmp_path):
    """Ensure skipping tutorial leaves all canvas tools, shapes, and colors fully operational."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_cap_cls.return_value = mock_cap

    cfg_file = str(tmp_path / "config.json")
    app = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)
    app.skip_tutorial()

    assert app.state == AppState.DRAWING
    assert app.canvas is not None

    # Test full canvas operation after skip
    canvas = app.canvas
    canvas.push_point((100, 100))
    canvas.push_point((105, 105))
    canvas.end_drawing()
    assert len(canvas.lines) == 1

    # Undo must work
    assert canvas.can_undo
    canvas.undo()
    assert len(canvas.lines) == 0


@patch("airdraw.cv.VideoCapture")
def test_camera_initialization_failure_displays_error(mock_cap_cls, tmp_path):
    """Verify camera failure transitions cleanly to CAMERA_ERROR state."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    mock_cap_cls.return_value = mock_cap

    cfg_file = str(tmp_path / "config.json")
    app = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)
    app.start_drawing()

    assert app.state == AppState.CAMERA_ERROR
    assert "Could not open webcam" in app.error_message
    assert app.capture is None


@patch("airdraw.cv.VideoCapture")
@patch("airdraw.HandDetector")
def test_reopen_tutorial_safely_releases_camera(mock_detector, mock_cap_cls, tmp_path):
    """Verify reopening tutorial pauses drawing, releases webcam, and returns to ONBOARDING."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_cap_cls.return_value = mock_cap

    cfg_file = str(tmp_path / "config.json")
    app = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)
    app.start_drawing()
    assert app.state == AppState.DRAWING

    # User reopens tutorial
    app.reopen_tutorial()
    assert app.state == AppState.ONBOARDING
    assert app.capture is None
    assert app.detector is None
    # Release was called on capture
    mock_cap.release.assert_called()


@patch("airdraw.cv.VideoCapture")
@patch("airdraw.HandDetector")
def test_repeated_clicks_do_not_initialize_multiple_cameras(mock_detector, mock_cap_cls, tmp_path):
    """Verify rapid consecutive clicks on Start Drawing initialize the camera only once."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_cap_cls.return_value = mock_cap

    cfg_file = str(tmp_path / "config.json")
    app = AirDrawApp(camera_index=0, config_path=cfg_file, force_onboarding=True)

    # First click starts initialization
    app.start_drawing()
    # Simulated second rapid click while state is DRAWING/INITIALIZING
    app.start_drawing()

    # Capture and detector should be initialized exactly once
    assert mock_cap_cls.call_count == 1
    assert mock_detector.call_count == 1


# ---------------------------------------------------------------------------
# Preference Persistence Tests
# ---------------------------------------------------------------------------

def test_preference_persistence(tmp_path):
    """Test saving and loading onboarding completion preference."""
    cfg_file = str(tmp_path / "sub" / ".airdraw_config.json")

    assert not has_completed_onboarding(cfg_file)
    set_onboarding_completed(True, cfg_file)
    assert has_completed_onboarding(cfg_file)
    set_onboarding_completed(False, cfg_file)
    assert not has_completed_onboarding(cfg_file)


def test_handle_keypress_tutorial_trigger():
    """Verify 't' key triggers canvas.reopen_tutorial flag."""
    canvas = Canvas(480, 640)
    assert not getattr(canvas, "reopen_tutorial", False)

    handle_keypress(ord("t"), canvas)
    assert canvas.reopen_tutorial is True
