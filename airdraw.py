import os
from datetime import datetime
import numpy as np
import cv2 as cv
from hands import HandDetector
from canvas import Canvas
from persistence import save_project, export_png


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
    print(f"AirDraw initialized ({width}x{height})")
    print("Controls:")
    print("  [h / ?] Toggle interactive help & gesture guide")
    print("  [b] Toggle camera / whiteboard background")
    print("  [z / Ctrl+Z] Undo")
    print("  [y / Ctrl+Y] Redo")
    print("  [ [ / ] ] Decrease / Increase brush size")
    print("  [s / Ctrl+S] Save project & Export clean PNG")
    print("  [e] Export Transparent PNG")
    print("  [q / ESC] Quit")
    
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
            if stroke == ord('h') or stroke == ord('?'): # press 'h' or '?' to toggle help overlay
                canvas.toggle_help()
            elif stroke == 27 and canvas.show_help: # 'esc' closes help if open
                canvas.show_help = False
            elif stroke == ord('b'): # press 'b' to switch backgrounds (camera/black)
                canvas.switch_background()
            elif stroke == ord('z') or stroke == 26: # 'z' or Ctrl+Z: Undo
                canvas.undo()
            elif stroke == ord('y') or stroke == 25: # 'y' or Ctrl+Y: Redo
                canvas.redo()
            elif stroke == ord('['): # '[': Decrease brush size
                canvas.set_brush_size(canvas.brush_size - 2)
            elif stroke == ord(']'): # ']': Increase brush size
                canvas.set_brush_size(canvas.brush_size + 2)
            elif stroke == ord('s') or stroke == 19: # 's' or Ctrl+S: Save & Export PNG
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                proj_file = f"projects/airdraw_{ts}.json"
                png_file = f"exports/airdraw_{ts}.png"
                save_project(canvas, proj_file)
                export_png(canvas, png_file, transparent=False)
                canvas.set_status(f"Saved: {os.path.basename(png_file)}")
            elif stroke == ord('e'): # 'e': Export Transparent PNG
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                png_file = f"exports/airdraw_trans_{ts}.png"
                export_png(canvas, png_file, transparent=True)
                canvas.set_status(f"Exported: {os.path.basename(png_file)}")
            elif stroke == ord('q') or stroke == 27: # press 'q' or 'esc' to quit
                break
    finally:
        cap.release()
        detector.close()
        cv.destroyAllWindows()

if __name__ == '__main__':
    main()
