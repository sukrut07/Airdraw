"""
Command-pattern history management system for AirDraw.
Supports atomic Undo and Redo for lines, shapes, erasing, translation, and canvas clearing.
"""
from abc import ABC, abstractmethod
from typing import List, Any, Tuple


class Command(ABC):
    """Abstract base class for all reversible canvas actions."""

    @abstractmethod
    def undo(self, canvas: Any) -> None:
        """Revert the action on the canvas."""
        pass

    @abstractmethod
    def redo(self, canvas: Any) -> None:
        """Re-apply the action on the canvas."""
        pass


class AddLineCommand(Command):
    """Reversible command for adding a freehand stroke / line."""

    def __init__(self, line: Any):
        self.line = line

    def undo(self, canvas: Any) -> None:
        if isinstance(canvas.lines, list):
            if self.line in canvas.lines:
                canvas.lines.remove(self.line)
        elif isinstance(canvas.lines, dict):
            # Dict backward compatibility
            to_del = [k for k, v in canvas.lines.items() if v == self.line]
            for k in to_del:
                del canvas.lines[k]

    def redo(self, canvas: Any) -> None:
        if isinstance(canvas.lines, list):
            if self.line not in canvas.lines:
                canvas.lines.append(self.line)
        elif isinstance(canvas.lines, dict):
            origin = self.line.get_origin()
            if origin:
                canvas.lines[origin] = self.line


class AddCircleCommand(Command):
    """Reversible command for creating a circle."""

    def __init__(self, circle: Any):
        self.circle = circle

    def undo(self, canvas: Any) -> None:
        if self.circle in canvas.circles:
            canvas.circles.remove(self.circle)

    def redo(self, canvas: Any) -> None:
        if self.circle not in canvas.circles:
            canvas.circles.append(self.circle)


class AddSquareCommand(Command):
    """Reversible command for creating a rectangle/square."""

    def __init__(self, square: Any):
        self.square = square

    def undo(self, canvas: Any) -> None:
        if self.square in canvas.squares:
            canvas.squares.remove(self.square)

    def redo(self, canvas: Any) -> None:
        if self.square not in canvas.squares:
            canvas.squares.append(self.square)


class EraseCommand(Command):
    """Reversible command for erasing objects from the canvas."""

    def __init__(self, removed_lines: List[Any], removed_circles: List[Any], removed_squares: List[Any]):
        self.removed_lines = list(removed_lines)
        self.removed_circles = list(removed_circles)
        self.removed_squares = list(removed_squares)

    def undo(self, canvas: Any) -> None:
        # Restore lines
        if isinstance(canvas.lines, list):
            for line in self.removed_lines:
                if line not in canvas.lines:
                    canvas.lines.append(line)
        elif isinstance(canvas.lines, dict):
            for line in self.removed_lines:
                origin = line.get_origin()
                if origin:
                    canvas.lines[origin] = line

        # Restore circles
        for circle in self.removed_circles:
            if circle not in canvas.circles:
                canvas.circles.append(circle)

        # Restore squares
        for square in self.removed_squares:
            if square not in canvas.squares:
                canvas.squares.append(square)

    def redo(self, canvas: Any) -> None:
        # Remove lines again
        if isinstance(canvas.lines, list):
            for line in self.removed_lines:
                if line in canvas.lines:
                    canvas.lines.remove(line)
        elif isinstance(canvas.lines, dict):
            for line in self.removed_lines:
                to_del = [k for k, v in canvas.lines.items() if v == line]
                for k in to_del:
                    del canvas.lines[k]

        # Remove circles again
        for circle in self.removed_circles:
            if circle in canvas.circles:
                canvas.circles.remove(circle)

        # Remove squares again
        for square in self.removed_squares:
            if square in canvas.squares:
                canvas.squares.remove(square)


class TranslateCommand(Command):
    """Reversible command for moving/translating objects across the canvas."""

    def __init__(self, line_moves: List[Tuple[Any, List[Tuple[int, int]], List[Tuple[int, int]]]],
                 circle_moves: List[Tuple[Any, Tuple[int, int], Tuple[int, int]]],
                 square_moves: List[Tuple[Any, Tuple[Tuple[int, int], Tuple[int, int]], Tuple[Tuple[int, int], Tuple[int, int]]]]):
        # (object, old_points, new_points)
        self.line_moves = line_moves
        # (circle, old_origin, new_origin)
        self.circle_moves = circle_moves
        # (square, (old_anchor, old_opp), (new_anchor, new_opp))
        self.square_moves = square_moves

    def undo(self, canvas: Any) -> None:
        for line, old_pts, _ in self.line_moves:
            line.points = list(old_pts)
            if isinstance(canvas.lines, dict):
                # Update dict keys if applicable
                to_del = [k for k, v in canvas.lines.items() if v == line]
                for k in to_del:
                    del canvas.lines[k]
                canvas.lines[line.get_origin()] = line

        for circle, old_orig, _ in self.circle_moves:
            circle.origin = old_orig

        for square, (old_anchor, old_opp), _ in self.square_moves:
            square.anchor = old_anchor
            square.opposite = old_opp

    def redo(self, canvas: Any) -> None:
        for line, _, new_pts in self.line_moves:
            line.points = list(new_pts)
            if isinstance(canvas.lines, dict):
                to_del = [k for k, v in canvas.lines.items() if v == line]
                for k in to_del:
                    del canvas.lines[k]
                canvas.lines[line.get_origin()] = line

        for circle, _, new_orig in self.circle_moves:
            circle.origin = new_orig

        for square, _, (new_anchor, new_opp) in self.square_moves:
            square.anchor = new_anchor
            square.opposite = new_opp


class ClearCanvasCommand(Command):
    """Reversible command for clearing the canvas."""

    def __init__(self, saved_lines: Any, saved_circles: List[Any], saved_squares: List[Any]):
        if isinstance(saved_lines, dict):
            self.saved_lines = dict(saved_lines)
        else:
            self.saved_lines = list(saved_lines)
        self.saved_circles = list(saved_circles)
        self.saved_squares = list(saved_squares)

    def undo(self, canvas: Any) -> None:
        if isinstance(self.saved_lines, dict):
            canvas.lines = dict(self.saved_lines)
        else:
            canvas.lines = list(self.saved_lines)
        canvas.circles = list(self.saved_circles)
        canvas.squares = list(self.saved_squares)

    def redo(self, canvas: Any) -> None:
        if isinstance(canvas.lines, dict):
            canvas.lines = {}
        else:
            canvas.lines = []
        canvas.circles = []
        canvas.squares = []


class DrawingHistory:
    """
    Manages the Undo/Redo stacks for canvas actions.
    Ensures safe operations, limits stack depth, and invalidates redo on new actions.
    """

    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []

    def push(self, command: Command) -> None:
        """Records a new completed action and clears the redo branch."""
        self.undo_stack.append(command)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, canvas: Any) -> bool:
        """Undoes the most recent action. Returns True if undone, False if nothing to undo."""
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.undo(canvas)
        self.redo_stack.append(cmd)
        return True

    def redo(self, canvas: Any) -> bool:
        """Redoes the most recently reverted action. Returns True if redone, False if nothing to redo."""
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.redo(canvas)
        self.undo_stack.append(cmd)
        return True

    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
