# 🚀 How to Run AirDraw

This guide provides simple, copy-pasteable commands to run **AirDraw** on your system.

---

### ⚡ Option 1: One-Command Automated Launch (macOS & Linux)

Simply run the included launcher script, which automatically selects Python 3.11, configures a virtual environment, installs dependencies, and starts the camera:

```bash
./run.sh
```

---

### 🛠️ Option 2: Manual Step-by-Step Launch

#### 🍎 macOS & 🐧 Linux

1. **Open your terminal** and navigate to the project directory:
   ```bash
   cd Airdraw
   ```

2. **Create a virtual environment with Python 3.11** *(recommended for MediaPipe)*:
   ```bash
   python3.11 -m venv venv
   ```
   *(If `python3.11` is not available, use `python3 -m venv venv`)*

3. **Activate the virtual environment**:
   ```bash
   source venv/bin/activate
   ```

4. **Install required dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Run the automated test suite**:
   ```bash
   pytest
   ```

6. **Run AirDraw**:
   ```bash
   python airdraw.py
   ```

---

#### 🪟 Windows (Command Prompt or PowerShell)

1. **Create and activate virtual environment**:
   ```cmd
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```cmd
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Run the test suite**:
   ```cmd
   pytest
   ```

4. **Run AirDraw**:
   ```cmd
   python airdraw.py
   ```

---

### 🎓 First-Launch Onboarding Experience

When you launch AirDraw, a clean, dark-mode **Pre-Camera Onboarding Screen** appears before your webcam feed or MediaPipe starts:

- **What it teaches**: A 3-step interactive tutorial with procedural vector illustrations covering:
  1. **Navigate & Draw**: 1-finger index cursor hover and 2-finger drawing.
  2. **Tools & Erase**: Selecting Line, Circle, Square tools, choosing from 6 colors, and touchless erasing with a closed fist or 3 fingers.
  3. **Move & Shortcuts**: Moving existing artwork across canvas (open palm or horns), 25-frame dwell clear, and rapid keyboard commands.
- **Start Drawing**: Click the high-contrast **Start Drawing ->** button or press <kbd>Enter</kbd> / <kbd>Space</kbd> to initialize camera capture and start drawing.
- **Skip Tutorial**: Click the **Skip Tutorial** button at the bottom of the screen or press <kbd>Tab</kbd> / <kbd>s</kbd> to jump straight into the drawing canvas. Both buttons share the exact same camera initialization path.
- **Reopen Guide Anytime**: While drawing, press <kbd>t</kbd> to pause and return to the full Onboarding Tutorial, or press <kbd>h</kbd> for the quick on-screen HUD guide.
- **CLI Options**:
  - `python airdraw.py --onboarding`: Force display of the onboarding tutorial.
  - `python airdraw.py --no-onboarding`: Bypass onboarding directly into the camera canvas.
  - `python airdraw.py --camera 1`: Use an external webcam at device index 1.

---

### 🎮 In-App Gestures & Keyboard Controls

#### 🖐️ Hand Gestures
- **Hover / Select**: Raise your **index finger** only. Move the cursor over the top toolbar to choose a color or drawing tool.
- **Draw**: Raise **index + middle fingers** together. Move to draw strokes, circles, or rectangles.
- **Erase**: Form a **closed fist** or raise **3 fingers** to wipe drawings within the yellow eraser radius.
- **Translate**: Open your hand (all five fingers extended) or form the horns pose (index + pinky extended) to move drawings.
- **Clear canvas**: Hold your index fingertip over `CLEAR` for 25 consecutive frames (~0.8s). The clear action can be undone.

#### ⌨️ Keyboard Shortcuts
- <kbd>t</kbd>: Open full **Onboarding Tutorial & Gesture Guide** (cleanly releases camera)
- <kbd>h</kbd> or <kbd>?</kbd>: Toggle interactive in-app help HUD overlay
- <kbd>b</kbd>: Toggle canvas background between **Live Camera** and **Black whiteboard**
- <kbd>z</kbd> / <kbd>Ctrl+Z</kbd>: Undo last drawing or clear action
- <kbd>y</kbd> / <kbd>Ctrl+Y</kbd>: Redo undone action
- <kbd>[</kbd> / <kbd>]</kbd>: Decrease / increase brush size (1px to 30px)
- <kbd>s</kbd> / <kbd>Ctrl+S</kbd>: Save editable JSON project and export clean PNG image
- <kbd>e</kbd>: Export transparent PNG (artwork only, no background)
- <kbd>q</kbd> / <kbd>ESC</kbd>: Quit AirDraw (or close help overlay if open)

---

### 🔧 Camera Troubleshooting

If AirDraw displays a **Camera Initialization Failed** error screen:
1. **Camera Permissions**:
   - On **macOS**: Go to `System Settings -> Privacy & Security -> Camera` and ensure Terminal / your IDE is granted camera access.
   - On **Windows**: Go to `Settings -> Privacy & security -> Camera` and enable camera access for desktop apps.
2. **Device in Use**: Make sure no other application (Zoom, Teams, FaceTime, Photo Booth, browser) is using your webcam.
3. **External Webcams**: If using an external USB camera, specify its index using `python airdraw.py --camera 1`.
4. **Retry & Recovery**: Click **Retry Camera [R]** on screen, or click **Back to Guide [B]** to review gestures while troubleshooting.

