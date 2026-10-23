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

### 🎮 In-App Gestures & Keyboard Controls

#### 🖐️ Hand Gestures
- **Hover / Select**: Raise your **index finger** only. Move the cursor over the top toolbar to choose a color or drawing tool.
- **Draw**: Raise **index + middle fingers** together. Move to draw strokes, circles, or rectangles.
- **Erase**: Form a **closed fist** or raise **3 fingers** to wipe drawings within the yellow eraser radius.
- **Translate**: Open your **whole hand** (5 fingers) or form horns to grab and move existing artwork.
- **Safe Clear All**: Hover your index finger over *Clear all* and hold for ~0.8s (a progress bar fills) to confirm wipe.

#### ⌨️ Keyboard Shortcuts
- <kbd>h</kbd> or <kbd>?</kbd>: Toggle interactive in-app help card & gesture guide
- <kbd>b</kbd>: Toggle canvas background between **Live Camera** and **Black whiteboard**
- <kbd>z</kbd> / <kbd>Ctrl+Z</kbd>: Undo last drawing action
- <kbd>y</kbd> / <kbd>Ctrl+Y</kbd>: Redo undone action
- <kbd>[</kbd> / <kbd>]</kbd>: Decrease / increase brush size
- <kbd>s</kbd> / <kbd>Ctrl+S</kbd>: Save editable JSON project and export clean PNG image
- <kbd>e</kbd>: Export transparent PNG (artwork only, no background)
- <kbd>q</kbd> / <kbd>ESC</kbd>: Quit AirDraw (or close help overlay if open)
