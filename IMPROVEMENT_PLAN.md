# AirDraw UI and Codebase Improvement Plan

This plan targets the current OpenCV HUD and gesture workflow. It deliberately keeps the lightweight Python/OpenCV/MediaPipe architecture rather than introducing a new UI framework before the core interactions are reliable.

## User-facing improvements

- Make tool labels easier to read and align them consistently.
- Visually separate **Clear canvas**, **Color**, and **Shape** controls.
- Show the active color and shape with a clear outline and a readable selected-state label.
- Improve status wording: use short action-oriented messages (for example, “Color set to BLUE”, “Brush size: 7 px”, “Canvas cleared — Undo available”).
- Keep help text consistent with actual gesture classification and keyboard shortcuts.
- Preserve hold-to-clear protection and keep clearing reversible with Undo.

## Reliability and maintainability

- Use `None` rather than a mutable dictionary as the default argument for optional gesture metadata.
- Keep camera and MediaPipe resources in `try/finally` cleanup paths.
- Fail clearly when webcam frames cannot be read.
- Avoid repeatedly emitting the same status message on every frame while hovering over one control.
- Keep tests for canvas state, gesture transitions, undo/redo, and export behavior passing.

## Repository hygiene

- Retain source modules, tests, CI, licensing, usage docs, and useful demo assets.
- Do not remove dataset recording tools or demo media solely because they are not imported by the main app; they may be intentional project utilities.
- Keep generated virtual environments, caches, recordings, exported images, and saved projects out of version control.
- Only delete files after confirming that they are generated or truly obsolete.

## Acceptance checklist

- [ ] The on-screen UI has clearer labels and control grouping.
- [ ] Hovering on a selected color or tool does not flood the status display.
- [ ] Tracking loss stops the current stroke and resets clear-button dwell state.
- [ ] Webcam and detector resources are closed on exit.
- [ ] Documentation matches the behavior implemented in code.
- [ ] Syntax checks and the automated tests pass.
