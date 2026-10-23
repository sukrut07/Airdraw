import numpy as np
import cv2 as cv
from hands import HandDetector
from canvas import Canvas


def replay(fname):
    print("replaying", fname)

    cap = cv.VideoCapture(fname)
    # Use whatever width and height possible
    frame_width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

    canvas = Canvas(height=frame_height, width=frame_width)

    if (not cap.isOpened()):
        print("Error opening video file")
        return

    detector = HandDetector()
    try:
        while cap.isOpened() and (cv.waitKey(0) & 0xFF != ord('q')):
            ret, img = cap.read()
            if ret:
                gesture_metadata = detector.get_gesture_metadata(img)
                img = canvas.update_and_draw(img, gesture_metadata)
                detector.draw_landmarks(img)
                cv.imshow('Camera', img)
            else:
                break
    finally:
        cap.release()
        detector.close()
        cv.destroyAllWindows()

    print("replay complete", fname)

def main():
    # Loading the default webcam of PC.
    cap = cv.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam (index 0). Please check camera permissions and connections.")
        return

    # width and height for 2-D grid
    width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH) + 0.5)
    height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT) + 0.5)

    # initialize the canvas element and hand-detector program
    canvas = Canvas(height=height, width=width)
    detector = HandDetector()
    print(f"Airdraw initialized ({width}x{height})")
    print("Controls: Press 'b' to toggle camera/black background, 'q' or ESC to quit")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("Warning: Failed to read frame from webcam.")
                break

            frame = cv.flip(frame, 1)

            gesture_metadata = detector.get_gesture_metadata(frame)

            frame = canvas.update_and_draw(frame, gesture_metadata)
            detector.draw_landmarks(frame)
           
            cv.imshow("Airdraw", frame)
        
            stroke = cv.waitKey(1) & 0xff  
            if stroke == ord('b'): # press 'b' to switch backgrounds (camera/black)
                canvas.switch_background()
            
            if stroke == ord('q') or stroke == 27: # press 'q' or 'esc' to quit
                break
    finally:
        cap.release()
        detector.close()
        cv.destroyAllWindows()

if __name__ == '__main__':
    main()
