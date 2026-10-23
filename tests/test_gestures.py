"""
Unit tests for HandDetector, LandmarkBuffer, gesture classification, and tracking loss handling.
"""
import pytest
from hands import Gesture, HandDetector, LandmarkBuffer


def create_mock_hand_landmarks(index_extended=True, middle_extended=False, ring_extended=False, pinky_extended=False):
    """
    Synthesizes a realistic 21-landmark hand in pixel coordinates (height=480, width=640).
    Wrist is at (idx, 300, 400).
    Fingers extend upwards (decreasing y / row) when extended,
    or curl back down towards palm (increasing y / row) when curled.
    """
    landmarks = []
    # 0: Wrist
    wrist_x, wrist_y = 300, 400
    landmarks.append((0, wrist_x, wrist_y))

    # 1-4: Thumb (default relaxed)
    landmarks.append((1, wrist_x - 30, wrist_y - 20))
    landmarks.append((2, wrist_x - 50, wrist_y - 50))
    landmarks.append((3, wrist_x - 60, wrist_y - 80))
    landmarks.append((4, wrist_x - 70, wrist_y - 100))

    # Helper for fingers: MCP, PIP, DIP, TIP
    def add_finger(mcp_idx, base_x, extended):
        mcp_y = wrist_y - 100
        landmarks.append((mcp_idx, base_x, mcp_y))
        if extended:
            # Points upwards away from wrist
            landmarks.append((mcp_idx + 1, base_x, mcp_y - 40))
            landmarks.append((mcp_idx + 2, base_x, mcp_y - 70))
            landmarks.append((mcp_idx + 3, base_x, mcp_y - 100))
        else:
            # Curled into palm
            landmarks.append((mcp_idx + 1, base_x, mcp_y - 20))
            landmarks.append((mcp_idx + 2, base_x, mcp_y + 10))
            landmarks.append((mcp_idx + 3, base_x, mcp_y + 30))

    # 5-8: Index
    add_finger(5, 270, index_extended)
    # 9-12: Middle
    add_finger(9, 300, middle_extended)
    # 13-16: Ring
    add_finger(13, 330, ring_extended)
    # 17-20: Pinky
    add_finger(17, 360, pinky_extended)

    return landmarks


def test_landmark_buffer_operations():
    buf = LandmarkBuffer(max_size=3)
    assert len(buf.buf) == 0

    l1 = [(i, 10, 20) for i in range(21)]
    buf.push_landmark(l1)
    assert len(buf.buf) == 1

    l2 = [(i, 20, 40) for i in range(21)]
    buf.push_landmark(l2)
    avg = buf.average_landmarks()
    assert avg[0][1] == pytest.approx(15.0)
    assert avg[0][2] == pytest.approx(30.0)

    # Test displacement
    disp = buf.displacement()
    assert disp[0][1] == 10
    assert disp[0][2] == 20

    # Test clear
    buf.clear()
    assert len(buf.buf) == 0


def test_detect_gesture_hover():
    detector = HandDetector(mode=False)
    # Only index extended -> HOVER
    landmarks = create_mock_hand_landmarks(index_extended=True, middle_extended=False, ring_extended=False, pinky_extended=False)
    gesture = detector.detect_gesture(landmarks)
    assert gesture == Gesture.HOVER


def test_detect_gesture_draw():
    detector = HandDetector(mode=False)
    # Index and middle extended -> DRAW
    landmarks = create_mock_hand_landmarks(index_extended=True, middle_extended=True, ring_extended=False, pinky_extended=False)
    gesture = detector.detect_gesture(landmarks)
    assert gesture == Gesture.DRAW


def test_detect_gesture_erase():
    detector = HandDetector(mode=False)
    # Closed fist (all curled) -> ERASE
    fist_landmarks = create_mock_hand_landmarks(index_extended=False, middle_extended=False, ring_extended=False, pinky_extended=False)
    gesture_fist = detector.detect_gesture(fist_landmarks)
    assert gesture_fist == Gesture.ERASE

    # 3-finger pose (index, middle, ring extended) -> ERASE
    three_finger_landmarks = create_mock_hand_landmarks(index_extended=True, middle_extended=True, ring_extended=True, pinky_extended=False)
    gesture_three = detector.detect_gesture(three_finger_landmarks)
    assert gesture_three == Gesture.ERASE


def test_detect_gesture_translate():
    detector = HandDetector(mode=False)
    # Open palm (all fingers extended) -> TRANSLATE
    open_palm = create_mock_hand_landmarks(index_extended=True, middle_extended=True, ring_extended=True, pinky_extended=True)
    gesture_palm = detector.detect_gesture(open_palm)
    assert gesture_palm == Gesture.TRANSLATE


def test_tracking_loss_resets_buffer():
    detector = HandDetector(mode=False)
    # Push landmarks
    l1 = create_mock_hand_landmarks(True, False, False, False)
    detector.translation_buffer.push_landmark(l1)
    assert len(detector.translation_buffer.buf) > 0

    # Simulate missing hand frame (blank or no landmarks)
    # Calling get_gesture_metadata with empty or zero-hand frame should reset buffer
    meta = detector.get_gesture_metadata_from_landmarks([])
    assert meta.get('tracking') is False
    assert meta.get('gesture') == Gesture.NONE
    assert len(detector.translation_buffer.buf) == 0
