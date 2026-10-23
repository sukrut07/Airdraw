import cv2 as cv
import mediapipe as mp
import numpy as np
from enum import Enum
from collections import deque

from util import xy_euclidean_dist, vectorize, cos_angle

if not hasattr(mp, 'solutions'):
    raise ImportError(
        "MediaPipe 'solutions' module was not found. "
        "MediaPipe >= 0.10.15 / 1.x removed the legacy solutions API. "
        "Please install the compatible version: pip install 'mediapipe<=0.10.14'"
    )

class Gesture(Enum):
    NONE = 'NONE'
    DRAW = 'DRAW'
    HOVER = 'HOVER'
    ERASE = 'ERASE'
    TRANSLATE = 'TRANSLATE'

class LandmarkBuffer():
    """Helper RingBuffer class to abstract away averaging logic"""

    def __init__(self, max_size):
        self.buf = deque([], maxlen=max_size)

    def push_landmark(self, element):
        self.buf.append(element)
    
    def clear(self):
        self.buf.clear()
    
    def average_landmarks(self):
        assert(len(self.buf) > 0)
        res = [[0]*3 for i in range(21)]
        num_points = len(self.buf)
        
        for landmark in self.buf:
            for i, vec in enumerate(landmark):
                res[i][0] += vec[0]
                res[i][1] += vec[1]
                res[i][2] += vec[2]
        
        for i, vec in enumerate(res):
            res[i][0] /= num_points
            res[i][1] /= num_points
            res[i][2] /= num_points

        return res

    def displacement(self):
        """Calculates the residual from the last two landmarks"""
        res = [[0]*3 for i in range(21)]
        num_points = len(self.buf)
        if num_points < 2 or any([len(landmark) != 21 for landmark in self.buf]):
            return res
        
        for i in range(21):
            for j in range(3):
                res[i][j] = self.buf[-1][i][j] - self.buf[-2][i][j]
        return res

class HandDetector():
    """
    This class defines the interaction the program will have with Mediapipe. It is essentially a wrapper layer around MP.

    This class will define how Airdraw will be passing information to and receiving information from Mediapipe. 
    Successful implementation of this class should involve no image rendering, but rather just state transformation of hands, gestures, and other metadata used from Mediapipe.
    """

    def __init__(self, mode = False, max_hands = 1):
        # setup
        self.max_hands = max_hands
        self.mode = mode
        # hand drawing stuff
        self.hands = mp.solutions.hands.Hands(static_image_mode=self.mode, max_num_hands=self.max_hands)
        self.drawing = mp.solutions.drawing_utils
        self.hand_connections = mp.solutions.hands.HAND_CONNECTIONS
        # will be used for translation
        self.translation_buffer = LandmarkBuffer(5)
        self.gesture_history = deque(maxlen=4)
        self.current_gesture = Gesture.NONE
        self.results = None

    def close(self):
        """Safely release MediaPipe resources"""
        if hasattr(self, 'hands') and self.hands:
            self.hands.close()

    def detect_landmarks(self, frame):
        """
        Noting all the points of one's hand in the image.

        args:
            - frame: np array representing image input. used to resize the prediction against mediapipe (will just use the builtin api soon though).
       returns:
            - list of landmarks on the hand in order of size and position
        """
        img_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB) # I think we need RGB
        self.results = self.hands.process(img_rgb)

        landmarks = []
        if self.results.multi_hand_landmarks:
            my_hand = self.results.multi_hand_landmarks[0] # should only be one
            for idx, landmark in enumerate(my_hand.landmark):
                height, width, _ = frame.shape
                x, y = int(landmark.x * width), int(landmark.y * height)
                landmarks.append((idx, x, y))

        return landmarks
    
    def draw_landmarks(self, img):
        """
        Draws hand landmarks on image. Breaks rules of class being only "img"->hand current state, but I think this looks the best so I'm keeping it this way.
        """
        if getattr(self, 'results', None) and self.results.multi_hand_landmarks:
            for hand_landmark in self.results.multi_hand_landmarks:
                self.drawing.draw_landmarks(img, hand_landmark, mp.solutions.hands.HAND_CONNECTIONS)

   
    def is_finger_extended(self, landmarks, mcp_idx, pip_idx, tip_idx, threshold=0.30):
        """
        Determines whether a finger is extended away from the wrist.
        Uses both angular alignment with the palm and radial distance from the wrist.
        """
        wrist = landmarks[0]
        mcp = landmarks[mcp_idx]
        pip = landmarks[pip_idx]
        tip = landmarks[tip_idx]

        pt_wrist = wrist[1:3] if len(wrist) == 3 else wrist[:2]
        pt_mcp = mcp[1:3] if len(mcp) == 3 else mcp[:2]
        pt_pip = pip[1:3] if len(pip) == 3 else pip[:2]
        pt_tip = tip[1:3] if len(tip) == 3 else tip[:2]

        palm_vec = vectorize(pt_wrist, pt_mcp)
        tip_vec = vectorize(pt_pip, pt_tip)

        cos_sim = cos_angle(palm_vec, tip_vec)
        dist_tip = xy_euclidean_dist(pt_wrist, pt_tip)
        dist_pip = xy_euclidean_dist(pt_wrist, pt_pip)

        return (cos_sim > threshold) and (dist_tip > dist_pip)

    def detect_gesture(self, landmarks, threshhold=0.30, debug=False):
        """
        Authoritative gesture classifier based on finger extensions:
        - HOVER / MOVE CURSOR: Index finger extended only
        - DRAW: Index and Middle fingers extended together
        - ERASE: Closed fist (all fingers curled) OR 3 fingers extended (Index, Middle, Ring)
        - TRANSLATE: Open palm (all fingers extended) OR Horns pose (Index + Pinky extended)
        - NONE: Transition or unclassified pose
        """
        if len(landmarks) < 21:
            return Gesture.NONE

        idx_ext = self.is_finger_extended(landmarks, 5, 6, 8, threshhold)
        mid_ext = self.is_finger_extended(landmarks, 9, 10, 12, threshhold)
        ring_ext = self.is_finger_extended(landmarks, 13, 14, 16, threshhold)
        pinky_ext = self.is_finger_extended(landmarks, 17, 18, 20, threshhold)

        if debug:
            return {'idx': idx_ext, 'mid': mid_ext, 'ring': ring_ext, 'pinky': pinky_ext}

        # 1. DRAW: Index + Middle extended, others curled
        if idx_ext and mid_ext and not ring_ext and not pinky_ext:
            return Gesture.DRAW

        # 2. ERASE: Closed fist OR 3 fingers extended (Index + Middle + Ring)
        if (not idx_ext and not mid_ext and not ring_ext and not pinky_ext) or \
           (idx_ext and mid_ext and ring_ext and not pinky_ext):
            return Gesture.ERASE

        # 3. TRANSLATE: Open hand (all fingers extended) OR Horns (Index + Pinky)
        if (idx_ext and mid_ext and ring_ext and pinky_ext) or \
           (idx_ext and pinky_ext and not mid_ext and not ring_ext):
            return Gesture.TRANSLATE

        # 4. HOVER: Index finger extended only
        if idx_ext and not mid_ext and not ring_ext and not pinky_ext:
            return Gesture.HOVER

        # Default fallback
        if idx_ext:
            return Gesture.HOVER

        return Gesture.NONE

    def get_gesture_metadata_from_landmarks(self, landmark_list):
        """
        Determines gesture state and coordinates from a 21-landmark list.
        Safely clears buffers and handles tracking loss when hand is absent.
        """
        if len(landmark_list) == 0 or np.sum(landmark_list) == 0:
            self.translation_buffer.clear()
            self.gesture_history.clear()
            self.current_gesture = Gesture.NONE
            return {
                'tracking': False,
                'gesture': Gesture.NONE,
                'idx_fing_tip': None,
                'mid_fing_tip': None,
                'ring_fing_tip': None,
                'pinky_fing_tip': None,
                'origin': None,
                'radius': None,
                'shift': None,
            }

        self.translation_buffer.push_landmark(landmark_list)
        average_landmark_list = self.translation_buffer.average_landmarks()
        raw_gesture = self.detect_gesture(average_landmark_list)

        # Temporal hysteresis: require confirmation across consecutive frames
        self.gesture_history.append(raw_gesture)
        if len(self.gesture_history) >= 2:
            if self.gesture_history[-1] == self.gesture_history[-2]:
                self.current_gesture = raw_gesture
        else:
            self.current_gesture = raw_gesture

        gesture = self.current_gesture

        def get_rc(lm):
            return (int(lm[2]), int(lm[1]))

        index_fing_tip = get_rc(average_landmark_list[8])
        mid_fing_tip = get_rc(average_landmark_list[12])
        ring_fing_tip = get_rc(average_landmark_list[16])
        pinky_fing_tip = get_rc(average_landmark_list[20])

        index_r, index_c = index_fing_tip
        mid_r, mid_c = mid_fing_tip
        ring_r, ring_c = ring_fing_tip
        pinky_r, pinky_c = pinky_fing_tip

        post = {
            'tracking': True,
            'gesture': gesture,
            'idx_fing_tip': index_fing_tip,
            'mid_fing_tip': mid_fing_tip,
            'ring_fing_tip': ring_fing_tip,
            'pinky_fing_tip': pinky_fing_tip,
            'origin': None,
            'radius': None,
            'shift': None,
        }

        if gesture == Gesture.DRAW:
            distance = xy_euclidean_dist(index_fing_tip, mid_fing_tip)
            midpoint_r = int((index_r + mid_r) * 0.5)
            midpoint_c = int((index_c + mid_c) * 0.5)
            post['origin'] = (midpoint_r, midpoint_c)
            post['radius'] = max(distance * 0.5, 8.0)

        elif gesture == Gesture.ERASE:
            if ring_fing_tip is not None and xy_euclidean_dist(index_fing_tip, ring_fing_tip) > 15:
                distance = xy_euclidean_dist(index_fing_tip, ring_fing_tip)
                midpoint_r = int((index_r + ring_r) * 0.5)
                midpoint_c = int((index_c + ring_c) * 0.5)
                radius = max(distance * 0.5, 25.0)
            else:
                midpoint_r, midpoint_c = int(index_r), int(index_c)
                radius = 35.0
            post['origin'] = (midpoint_r, midpoint_c)
            post['radius'] = radius

        elif gesture == Gesture.TRANSLATE:
            distance = xy_euclidean_dist(index_fing_tip, pinky_fing_tip)
            midpoint_r = int((index_r + pinky_r) * 0.5)
            midpoint_c = int((index_c + pinky_c) * 0.5)
            post['origin'] = (midpoint_r, midpoint_c)
            post['radius'] = max(distance * 0.5, 30.0)

            displacement = self.translation_buffer.displacement()
            index_displacement = displacement[8]
            post['shift'] = (index_displacement[2], index_displacement[1])

        elif gesture == Gesture.HOVER:
            post['origin'] = (index_r, index_c)
            post['radius'] = 8.0

        return post

    def get_gesture_metadata(self, frame):
        """
        Calls MediaPipe on frame and returns metadata dictionary about detected gesture.
        """
        landmark_list = self.detect_landmarks(frame)
        return self.get_gesture_metadata_from_landmarks(landmark_list)

def replay(fname):
    print("replaying", fname)

    cap = cv.VideoCapture(fname)
    detector = HandDetector()

    if (not cap.isOpened()):
        print("Error opening video file")
        return

    while cap.isOpened() and (cv.waitKey(0) & 0xFF != ord('q')):
        ret, img = cap.read()

        # replay is completed when the video capture no longer has any frames to read.
        if ret:
            landmark_list = detector.detect_landmarks(img)
            detector.draw_landmarks(img)

            if len(landmark_list) != 0:
                val = detector.detect_gesture(landmark_list, threshhold=0.9)
                cv.putText(img, f"Mode: {val.value}", (50, 50),
                        cv.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv.LINE_AA)



            cv.imshow('Camera', img)
        else:
            break

    cap.release()
    cv.destroyAllWindows()

    print("replay complete", fname)

def live_demo():
    cap = cv.VideoCapture(0)
    detector = HandDetector()

    while True:
        _, img = cap.read()
        img = cv.flip(img, 1)

        landmark_list = detector.detect_landmarks(img)

        detector.draw_landmarks(img)

        if len(landmark_list) != 0:
            val = detector.detect_gesture(landmark_list, threshhold=0.9)
            cv.putText(img, f"Mode: {val.value}", (50, 50),
                    cv.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv.LINE_AA)

        cv.imshow('Camera', img)
        if cv.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv.destroyAllWindows()


if __name__ == "__main__":
    import sys
    import os
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        replay(sys.argv[1])
    else:
        print("Starting live hand tracking demo (press 'q' to quit)...")
        live_demo()
