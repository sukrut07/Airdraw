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

1. **Open your terminal** and navigate to the project root:
   ```bash
   cd "/Users/sukrutdusane/Documents/Projects /Sy/airdraw-main"
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

5. **Run AirDraw**:
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

3. **Run AirDraw**:
   ```cmd
   python airdraw.py
   ```

---

### 🎮 In-App Controls & Gestures

- **Draw**: Raise your **index finger** only.
- **Hover / Select**: Raise **index + middle fingers**. Hover over top buttons to pick color or shape, or click *Clear All*.
- **Erase**: Form a **closed fist** over drawings you want to wipe.
- **Translate**: Open your **whole hand** (5 fingers) to move shapes around.
- **Background Switch**: Press <kbd>b</kbd> to toggle between your live camera view and a solid black canvas.
- **Quit**: Press <kbd>q</kbd> or <kbd>ESC</kbd>.
