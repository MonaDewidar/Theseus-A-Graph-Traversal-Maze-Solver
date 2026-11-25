"""Theseus - an interactive graph-traversal maze solver.

Watch BFS, DFS, Dijkstra and A* explore a randomly generated maze, edit the
maze with the mouse and compare the algorithms side by side.

Run with:  python main.py
"""

import contextlib
import logging
import sys
import time
from collections import namedtuple

try:
    import pygame
except ImportError:
    sys.stderr.write(
        "Theseus needs pygame to run.\nInstall it with:  python -m pip install pygame-ce\n"
    )
    sys.exit(1)

try:
    from Algorithms import ALGORITHMS, path_cost
    from Grid import Grid
    from Maze_Generation import (
        DEFAULT_WEIGHT,
        add_random_weights,
        clear_weights,
        maze_generation,
    )
except ImportError as import_error:
    sys.stderr.write(
        f"Theseus could not load one of its modules: {import_error}\n"
        "Make sure Algorithms.py, Grid.py and Maze_Generation.py are next to main.py.\n"
    )
    sys.exit(1)

log = logging.getLogger("theseus")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
TITLE = "Theseus — Graph Traversal Maze Solver"
ROWS, COLS = 25, 41
CELL = 22
FPS = 60

SIDEBAR_W = 300
SIDE_PAD = 24
CONTENT_W = SIDEBAR_W - 2 * SIDE_PAD
GAP = 8
BUTTON_H = 32
SOLVE_H = 38
PAD = 20
LEGEND_H = 40
STATUS_H = 32

# Vertical positions of the sidebar sections (algorithm buttons are laid out two per row).
ALGO_ROWS = max(1, (len(ALGORITHMS) + 1) // 2)
Y_ALGO_HEADER = 84
Y_ALGO_BUTTONS = Y_ALGO_HEADER + 20
Y_DESCRIPTION = Y_ALGO_BUTTONS + ALGO_ROWS * (BUTTON_H + GAP) + 4
Y_TAGS = Y_DESCRIPTION + 40
Y_CONTROLS_HEADER = Y_TAGS + 36
Y_SOLVE = Y_CONTROLS_HEADER + 20
Y_ROW_1 = Y_SOLVE + SOLVE_H + GAP
Y_ROW_2 = Y_ROW_1 + BUTTON_H + GAP
Y_SPEED_HEADER = Y_ROW_2 + BUTTON_H + 18
Y_SLIDER = Y_SPEED_HEADER + 22
Y_STATS_HEADER = Y_SLIDER + 30
Y_STATS = Y_STATS_HEADER + 20
TILE_H = 38
TILE_GAP = 6
SIDEBAR_MIN_H = Y_STATS + 3 * TILE_H + 2 * TILE_GAP + 12

# The window fits the maze, but never gets shorter than the sidebar content.
GRID_X = SIDEBAR_W + PAD
GRID_Y = PAD + LEGEND_H
GRID_W = COLS * CELL
GRID_H = ROWS * CELL
WIDTH = GRID_X + GRID_W + PAD
HEIGHT = max(GRID_Y + GRID_H + PAD, SIDEBAR_MIN_H) + STATUS_H
SIDEBAR_H = HEIGHT - STATUS_H

# Animation speed levels, in expanded cells per second (None = instant).
SPEED_STEPS = (2, 5, 10, 20, 40, 80, 160, 320, 640, None)
DEFAULT_SPEED = 6
MAX_FRAME_TIME = 0.1

FONT_NAMES = "segoeui,helveticaneue,helvetica,arial,dejavusans,liberationsans"

# Search states.
IDLE, RUNNING, PAUSED, DONE = "idle", "running", "paused", "done"

# Mouse editing modes.
DRAW_WALL, ERASE, PAINT_WEIGHT, REMOVE_WEIGHT = "wall", "erase", "weight", "unweight"
MOVE_START, MOVE_END = "move_start", "move_end"


class Color:
    WHITE = (255, 255, 255)
    BG = (11, 15, 25)
    SIDEBAR = (16, 21, 34)
    PANEL = (23, 29, 45)
    PANEL_ALT = (28, 35, 54)
    BORDER = (39, 47, 68)
    BORDER_SOFT = (30, 37, 55)
    TEXT = (226, 232, 240)
    MUTED = (148, 163, 184)
    DIM = (100, 116, 139)
    ACCENT = (99, 102, 241)
    ACCENT_HOVER = (129, 140, 248)
    ACCENT_PRESSED = (79, 70, 229)
    ACCENT_TEXT = (199, 210, 254)
    BUTTON = (30, 38, 58)
    BUTTON_HOVER = (41, 51, 77)
    BUTTON_DISABLED = (21, 27, 42)
    SELECTED = (45, 44, 110)
    SELECTED_HOVER = (55, 54, 130)
    GRID_LINE = (20, 25, 39)
    FLOOR = (35, 43, 64)
    WALL = (6, 9, 16)
    VISITED = (37, 78, 150)
    FRONTIER = (45, 212, 191)
    PATH = (250, 204, 21)
    START = (34, 197, 94)
    END = (244, 63, 94)
    WEIGHT = (192, 132, 252)
    WEIGHT_ON_PATH = (107, 33, 168)
    HOVER = (203, 213, 225)
    SUCCESS = (74, 222, 128)
    WARNING = (251, 191, 36)
    ERROR = (248, 113, 113)
    OVERLAY = (4, 6, 12, 185)


STATUS_COLORS = {
    "info": Color.MUTED,
    "success": Color.SUCCESS,
    "warning": Color.WARNING,
    "error": Color.ERROR,
}

AlgoInfo = namedtuple("AlgoInfo", "title description tags")

ALGO_INFO = {
    "BFS": AlgoInfo(
        "Breadth-First Search",
        "Explores level by level, so the first path it finds uses the fewest moves.",
        (("Unweighted", Color.MUTED), ("Fewest moves", Color.SUCCESS)),
    ),
    "DFS": AlgoInfo(
        "Depth-First Search",
        "Dives down one corridor at a time, then backtracks. Fast, but not optimal.",
        (("Unweighted", Color.MUTED), ("Not optimal", Color.WARNING)),
    ),
    "Dijkstra": AlgoInfo(
        "Dijkstra's Algorithm",
        "Always expands the cheapest cell next, giving the lowest-cost path.",
        (("Weighted", Color.WEIGHT), ("Optimal", Color.SUCCESS)),
    ),
    "A*": AlgoInfo(
        "A* Search",
        "Dijkstra steered by a distance heuristic: lowest cost, fewer cells explored.",
        (
            ("Weighted", Color.WEIGHT),
            ("Optimal", Color.SUCCESS),
            ("Heuristic", Color.ACCENT_HOVER),
        ),
    ),
}

LEGEND = (
    ("Start", "start"),
    ("End", "end"),
    ("Wall", "wall"),
    (f"Weight ({DEFAULT_WEIGHT})", "weight"),
    ("Frontier", "frontier"),
    ("Visited", "visited"),
    ("Path", "path"),
)

HELP_KEYS = (
    ("Space", "Solve / pause / resume"),
    ("S", "Advance one step"),
    ("R", "Reset the search"),
    ("N", "Generate a new maze"),
    ("W", "Toggle random weights"),
    ("X", "Clear the board"),
    ("C", "Compare all algorithms"),
    (f"1 - {min(9, len(ALGORITHMS))}", "Choose an algorithm"),
    ("+ / -", "Faster / slower"),
    ("H", "Show this help"),
    ("Esc", "Close dialog / pause"),
)

HELP_MOUSE = (
    ("Left drag", "Draw or erase walls"),
    ("Right drag", "Erase walls and weights"),
    ("Shift + drag", f"Paint weights (cost {DEFAULT_WEIGHT})"),
    ("Drag S / E", "Move the start or end"),
)

HELP_TIP = (
    "Editing the maze clears the current search. Weighted cells only change "
    "the result of Dijkstra and A*; BFS and DFS count every move as 1."
)

CompareResult = namedtuple("CompareResult", "name visited length cost millis error")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def load_font(size, bold=False):
    """Load a clean system font, falling back to pygame's built-in font."""
    try:
        return pygame.font.SysFont(FONT_NAMES, size, bold=bold)
    except Exception:  # Broken font registries raise all sorts of errors.
        log.warning("System font unavailable, using the default font.")
        font = pygame.font.Font(None, size + 6)
        font.set_bold(bold)
        return font


def mix(color_a, color_b, amount):
    """Blend two RGB colors; amount=0 gives color_a, amount=1 gives color_b."""
    return tuple(round(a + (b - a) * amount) for a, b in zip(color_a, color_b))


def fit_text(font, text, max_width):
    """Shorten text with an ellipsis so it fits in max_width pixels."""
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    while text and font.size(text + "…")[0] > max_width:
        text = text[:-1]
    return text.rstrip() + "…" if text else ""


def wrap_text(font, text, max_width, max_lines=None):
    """Split text into lines no wider than max_width pixels."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    if max_lines is not None and len(lines) > max_lines:
        kept = lines[:max_lines]
        kept[-1] = fit_text(font, " ".join(lines[max_lines - 1 :]), max_width)
        lines = kept
    return [fit_text(font, line, max_width) for line in lines]


def cells_between(start, end):
    """Grid positions on a straight line from start (exclusive) to end (inclusive)."""
    (r0, c0), (r1, c1) = start, end
    steps = max(abs(r1 - r0), abs(c1 - c0))
    for i in range(1, steps + 1):
        t = i / steps
        yield round(r0 + (r1 - r0) * t), round(c0 + (c1 - c0) * t)


def draw_logo(surface, rect):
    """Draw the application mark: a winding route from a start to a goal."""
    pygame.draw.rect(surface, Color.ACCENT, rect, border_radius=max(4, rect.width // 4))
    size = rect.width
    thickness = max(2, size // 9)
    route = ((0.28, 0.28), (0.72, 0.28), (0.72, 0.50), (0.28, 0.50), (0.28, 0.72), (0.60, 0.72))
    for (x1, y1), (x2, y2) in zip(route, route[1:]):
        left = rect.x + round(min(x1, x2) * size) - thickness // 2
        top = rect.y + round(min(y1, y2) * size) - thickness // 2
        width = round(abs(x2 - x1) * size) + thickness
        height = round(abs(y2 - y1) * size) + thickness
        surface.fill(Color.WHITE, (left, top, width, height))
    start = (rect.x + round(0.28 * size), rect.y + round(0.28 * size))
    goal = (rect.x + round(0.74 * size), rect.y + round(0.72 * size))
    pygame.draw.circle(surface, Color.START, start, max(2, size // 10))
    pygame.draw.circle(surface, Color.PATH, goal, max(2, size // 9))


def make_window_icon():
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    draw_logo(icon, icon.get_rect())
    return icon


class TextCache:
    """Caches rendered text so it is not re-rasterised every frame."""

    def __init__(self, limit=600):
        self._cache = {}
        self._limit = limit

    def render(self, font, text, color):
        key = (id(font), text, color)
        surface = self._cache.get(key)
        if surface is None:
            if len(self._cache) >= self._limit:
                self._cache.clear()
            surface = font.render(text, True, color)
            self._cache[key] = surface
        return surface


class Fonts:
    def __init__(self):
        self.title = load_font(22, bold=True)
        self.heading = load_font(18, bold=True)
        self.body = load_font(14)
        self.body_bold = load_font(14, bold=True)
        self.button = load_font(13)
        self.button_bold = load_font(14, bold=True)
        self.small = load_font(12)
        self.small_bold = load_font(12, bold=True)
        self.label = load_font(11, bold=True)
        self.value = load_font(17, bold=True)
        self.cell = load_font(max(9, int(CELL * 0.5)), bold=True)


class Button:
    def __init__(self, rect, label, action, primary=False, hotkey=""):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.primary = primary
        self.hotkey = hotkey
        self.icon = None
        self.enabled = True
        self.selected = False

    def contains(self, pos):
        return self.enabled and self.rect.collidepoint(pos)


class Slider:
    def __init__(self, rect, minimum, maximum, value):
        self.rect = pygame.Rect(rect)
        self.minimum = minimum
        self.maximum = maximum
        self.value = value
        self.dragging = False

    def contains(self, pos):
        return self.rect.inflate(18, 14).collidepoint(pos)

    def value_at(self, x):
        ratio = (x - self.rect.left) / max(1, self.rect.width)
        ratio = min(1.0, max(0.0, ratio))
        return self.minimum + round(ratio * (self.maximum - self.minimum))

    def handle_x(self):
        span = max(1, self.maximum - self.minimum)
        return self.rect.left + round((self.value - self.minimum) / span * self.rect.width)


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
class App:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        self.texts = TextCache()
        self.dim_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.dim_layer.fill(Color.OVERLAY)

        self.grid = Grid(ROWS, COLS)
        self.algorithm = next(iter(ALGORITHMS))
        self.visited = set()
        self.frontier = set()
        self.path = []
        self.search = None
        self.state = IDLE
        self.compute_time = 0.0
        self.reveal = 0.0
        self.step_budget = 0.0
        self.speed = DEFAULT_SPEED
        self.weighted = False
        self.open_cells = 0

        self.overlay = None
        self.overlay_card = pygame.Rect(0, 0, 0, 0)
        self.overlay_close = pygame.Rect(0, 0, 0, 0)
        self.compare_results = []

        self.status_text = ""
        self.status_level = "info"
        self.edit_mode = None
        self.edit_button = None
        self.last_edit_cell = None
        self.pressed_button = None
        self.cursor = None
        self.cursors_supported = True
        self.running = True

        self._build_widgets()
        self.new_maze(announce=False)
        self.set_status("Ready. Pick an algorithm and press Solve (Space). Press H for help.")

    # ------------------------------------------------------------------ setup
    def _build_widgets(self):
        x = SIDE_PAD
        half = (CONTENT_W - GAP) // 2
        third = (CONTENT_W - 2 * GAP) // 3
        last_third = CONTENT_W - 2 * (third + GAP)

        self.algo_buttons = {}
        for index, name in enumerate(ALGORITHMS):
            col, row = index % 2, index // 2
            rect = (
                x + col * (half + GAP),
                Y_ALGO_BUTTONS + row * (BUTTON_H + GAP),
                half if col == 0 else CONTENT_W - half - GAP,
                BUTTON_H,
            )
            hotkey = str(index + 1) if index < 9 else ""
            self.algo_buttons[name] = Button(
                rect, name, lambda n=name: self.select_algorithm(n), hotkey=hotkey
            )

        self.solve_button = Button(
            (x, Y_SOLVE, CONTENT_W, SOLVE_H),
            "Solve",
            self.toggle_run,
            primary=True,
            hotkey="Space",
        )
        self.step_button = Button((x, Y_ROW_1, third, BUTTON_H), "Step", self.step_once)
        self.reset_button = Button(
            (x + third + GAP, Y_ROW_1, third, BUTTON_H), "Reset", self.reset_search
        )
        self.compare_button = Button(
            (x + 2 * (third + GAP), Y_ROW_1, last_third, BUTTON_H),
            "Compare",
            self.compare_all,
        )
        self.maze_button = Button((x, Y_ROW_2, third, BUTTON_H), "New maze", self.new_maze)
        self.weights_button = Button(
            (x + third + GAP, Y_ROW_2, third, BUTTON_H), "Weights", self.toggle_weights
        )
        self.clear_button = Button(
            (x + 2 * (third + GAP), Y_ROW_2, last_third, BUTTON_H),
            "Clear",
            self.clear_board,
        )

        self.buttons = [
            *self.algo_buttons.values(),
            self.solve_button,
            self.step_button,
            self.reset_button,
            self.compare_button,
            self.maze_button,
            self.weights_button,
            self.clear_button,
        ]
        self.slider = Slider(
            (x + 8, Y_SLIDER, CONTENT_W - 16, 16), 1, len(SPEED_STEPS), self.speed
        )

    # ------------------------------------------------------------- main loop
    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, MAX_FRAME_TIME)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def set_status(self, text, level="info"):
        self.status_text = text
        self.status_level = level if level in STATUS_COLORS else "info"

    def run_action(self, action):
        """Run a user action, turning unexpected errors into a status message."""
        try:
            action()
        except Exception as error:
            log.exception("Action failed")
            self.edit_mode = None
            self.set_status(f"Something went wrong: {error}", "error")

    @property
    def info(self):
        return ALGO_INFO.get(self.algorithm, AlgoInfo(self.algorithm, "", ()))

    # ----------------------------------------------------------- grid state
    def _grid_changed(self):
        self.weighted = self.grid.has_weights()
        self.open_cells = sum(1 for cell in self.grid.get_all() if not cell.is_wall)

    def new_maze(self, announce=True):
        keep_weights = self.weighted
        self.reset_search(quiet=True)
        try:
            maze_generation(self.grid)
            if keep_weights:
                add_random_weights(self.grid)
        except Exception as error:
            log.exception("Maze generation failed")
            self.grid.clear()
            self.set_status(
                f"Could not generate a maze ({error}). Showing an empty board.", "error"
            )
        else:
            if announce:
                self.set_status("New maze generated.")
        self._grid_changed()

    def clear_board(self):
        self.reset_search(quiet=True)
        self.grid.clear()
        self._grid_changed()
        self.set_status("Board cleared. Drag with the left mouse button to draw walls.")

    def toggle_weights(self):
        self.reset_search(quiet=True)
        if self.weighted:
            clear_weights(self.grid)
            self.set_status("Weights removed. Every move now costs 1.")
        else:
            add_random_weights(self.grid)
            self.set_status(
                f"Random weights added: purple cells cost {DEFAULT_WEIGHT} to enter. "
                "Try Dijkstra or A*."
            )
        self._grid_changed()

    # --------------------------------------------------------------- search
    def select_algorithm(self, name):
        if name not in ALGORITHMS:
            self.set_status(f"Unknown algorithm: {name}", "error")
            return
        if name == self.algorithm:
            return
        had_search = self.state != IDLE
        self.algorithm = name
        self.reset_search(quiet=True)
        message = f"Selected {self.info.title}."
        if had_search:
            message += " The previous search was cleared."
        self.set_status(message)

    def _start_search(self):
        self.reset_search(quiet=True)
        self.search = ALGORITHMS[self.algorithm](self.grid, self.visited, self.frontier)

    def toggle_run(self):
        if self.state == RUNNING:
            self.state = PAUSED
            self.set_status("Paused. Press Space to resume or S to step.")
        elif self.state == PAUSED:
            self.state = RUNNING
            self.set_status(f"Running {self.info.title}…")
        else:
            self._start_search()
            self.state = RUNNING
            self.set_status(f"Running {self.info.title}…")
            if SPEED_STEPS[self.speed - 1] is None:
                self._advance(None)

    def step_once(self):
        if self.state == RUNNING:
            return
        if self.state in (IDLE, DONE):
            self._start_search()
        self.state = PAUSED
        self._advance(1)
        if self.state == PAUSED:
            self.set_status(
                f"Step {len(self.visited):,}: {len(self.frontier):,} cells waiting in the "
                "frontier."
            )

    def reset_search(self, quiet=False):
        if self.search is not None:
            self.search.close()
        self.search = None
        self.state = IDLE
        self.visited.clear()
        self.frontier.clear()
        self.path = []
        self.compute_time = 0.0
        self.reveal = 0.0
        self.step_budget = 0.0
        if not quiet:
            self.set_status("Search cleared.")

    def _advance(self, max_steps):
        """Advance the running search by max_steps cells (None = to the end)."""
        if self.search is None:
            return
        taken = 0
        started = time.perf_counter()
        try:
            while max_steps is None or taken < max_steps:
                next(self.search)
                taken += 1
        except StopIteration as finished:
            self.compute_time += time.perf_counter() - started
            self._finish(finished.value)
            return
        except Exception as error:
            log.exception("Search failed")
            self.search = None
            self.reset_search(quiet=True)
            self.set_status(f"{self.info.title} failed: {error}", "error")
            return
        self.compute_time += time.perf_counter() - started

    def _finish(self, result):
        self.search = None
        self.state = DONE
        self.path = list(result or [])
        instant = SPEED_STEPS[self.speed - 1] is None
        self.reveal = float(len(self.path)) if instant else 0.0

        if self.path:
            self.set_status(
                f"{self.info.title} found a path: {len(self.path) - 1:,} moves, "
                f"cost {path_cost(self.path):,}, {len(self.visited):,} cells explored.",
                "success",
            )
        else:
            self.set_status("No path exists: the end cannot be reached from the start.", "warning")

    def compare_all(self):
        if self.state == RUNNING:
            self.state = PAUSED
        results = []
        for name, algorithm in ALGORITHMS.items():
            visited, frontier = set(), set()
            started = time.perf_counter()
            try:
                search = algorithm(self.grid, visited, frontier)
                while True:
                    try:
                        next(search)
                    except StopIteration as finished:
                        path = list(finished.value or [])
                        break
            except Exception as error:
                log.exception("%s failed during comparison", name)
                results.append(CompareResult(name, 0, None, None, 0.0, str(error)))
                continue
            millis = (time.perf_counter() - started) * 1000
            if path:
                results.append(
                    CompareResult(name, len(visited), len(path) - 1, path_cost(path), millis, None)
                )
            else:
                results.append(CompareResult(name, len(visited), None, None, millis, None))

        self.compare_results = results
        self.overlay = "compare"
        solved = [r for r in results if r.error is None and r.cost is not None]
        if solved:
            fewest = min(solved, key=lambda r: r.visited)
            self.set_status(
                f"Comparison done: {fewest.name} explored the fewest cells.", "success"
            )
        else:
            self.set_status("Comparison done: no algorithm could reach the end.", "warning")

    def show_help(self):
        if self.state == RUNNING:
            self.state = PAUSED
            self.set_status("Paused while the help is open.")
        self.overlay = "help"

    def close_overlay(self):
        self.overlay = None

    def change_speed(self, delta):
        self.set_speed(self.speed + delta)

    def set_speed(self, value):
        value = max(1, min(len(SPEED_STEPS), value))
        if value == self.speed:
            return
        self.speed = value
        self.slider.value = value
        self.step_budget = 0.0
        if SPEED_STEPS[value - 1] is None and self.state == RUNNING:
            self._advance(None)

    def speed_label(self):
        steps = SPEED_STEPS[self.speed - 1]
        return "Instant" if steps is None else f"{steps:,} steps/s"

    # --------------------------------------------------------------- update
    def update(self, dt):
        if self.state == RUNNING:
            steps_per_second = SPEED_STEPS[self.speed - 1]
            if steps_per_second is None:
                self._advance(None)
            else:
                self.step_budget = min(
                    self.step_budget + dt * steps_per_second, steps_per_second * 0.25 + 1
                )
                steps = int(self.step_budget)
                if steps:
                    self.step_budget -= steps
                    self._advance(steps)

        if self.state == DONE and self.reveal < len(self.path):
            rate = max(45.0, len(self.path) / 1.2)
            self.reveal = min(float(len(self.path)), self.reveal + rate * dt)

        self._refresh_widgets()
        self._update_cursor(pygame.mouse.get_pos())

    def _refresh_widgets(self):
        for name, button in self.algo_buttons.items():
            button.selected = name == self.algorithm
        self.weights_button.selected = self.weighted
        self.step_button.enabled = self.state != RUNNING
        self.reset_button.enabled = self.state != IDLE

        labels = {
            IDLE: ("Solve", "play"),
            RUNNING: ("Pause", "pause"),
            PAUSED: ("Resume", "play"),
            DONE: ("Solve again", "play"),
        }
        self.solve_button.label, self.solve_button.icon = labels[self.state]

    def _update_cursor(self, mouse):
        if not self.cursors_supported:
            return
        wanted = pygame.SYSTEM_CURSOR_ARROW
        if self.overlay:
            if self.overlay_close.collidepoint(mouse):
                wanted = pygame.SYSTEM_CURSOR_HAND
        elif self.edit_mode in (MOVE_START, MOVE_END):
            wanted = pygame.SYSTEM_CURSOR_SIZEALL
        elif any(button.contains(mouse) for button in self.buttons) or (
            self.slider.contains(mouse) or self.slider.dragging
        ):
            wanted = pygame.SYSTEM_CURSOR_HAND
        else:
            cell = self._cell_at(mouse)
            if cell is self.grid.start or cell is self.grid.end:
                wanted = pygame.SYSTEM_CURSOR_SIZEALL
            elif cell is not None and self.grid.is_interior(cell.row, cell.col):
                wanted = pygame.SYSTEM_CURSOR_CROSSHAIR

        if wanted != self.cursor:
            try:
                pygame.mouse.set_cursor(wanted)
                self.cursor = wanted
            except (pygame.error, TypeError, AttributeError):
                self.cursors_supported = False

    # --------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self._on_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._on_mouse_up(event)
        elif event.type == pygame.MOUSEMOTION:
            self._on_mouse_move(event)
        elif event.type == pygame.MOUSEWHEEL:
            if not self.overlay and pygame.mouse.get_pos()[0] < SIDEBAR_W:
                self.change_speed(1 if event.y > 0 else -1 if event.y < 0 else 0)
        elif event.type == getattr(pygame, "WINDOWFOCUSLOST", None):
            self._end_edit()
            self.slider.dragging = False
            self.pressed_button = None

    def _on_key(self, event):
        key = event.key
        if self.overlay:
            if key in (
                pygame.K_ESCAPE,
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
                pygame.K_SPACE,
                pygame.K_h,
                pygame.K_F1,
                pygame.K_c,
            ):
                self.close_overlay()
            return

        if key == pygame.K_q and event.mod & pygame.KMOD_CTRL:
            self.running = False
            return

        number_keys = [
            pygame.K_1,
            pygame.K_2,
            pygame.K_3,
            pygame.K_4,
            pygame.K_5,
            pygame.K_6,
            pygame.K_7,
            pygame.K_8,
            pygame.K_9,
        ]
        keypad_keys = [getattr(pygame, f"K_KP{n}", None) for n in range(1, 10)]
        names = list(ALGORITHMS)
        for index, (digit, keypad) in enumerate(zip(number_keys, keypad_keys)):
            if key in (digit, keypad) and index < len(names):
                self.run_action(lambda n=names[index]: self.select_algorithm(n))
                return

        actions = {
            pygame.K_SPACE: self.toggle_run,
            pygame.K_s: self.step_once,
            pygame.K_RIGHT: self.step_once,
            pygame.K_r: self.reset_search,
            pygame.K_n: self.new_maze,
            pygame.K_w: self.toggle_weights,
            pygame.K_x: self.clear_board,
            pygame.K_c: self.compare_all,
            pygame.K_h: self.show_help,
            pygame.K_F1: self.show_help,
            pygame.K_EQUALS: lambda: self.change_speed(1),
            pygame.K_PLUS: lambda: self.change_speed(1),
            pygame.K_KP_PLUS: lambda: self.change_speed(1),
            pygame.K_UP: lambda: self.change_speed(1),
            pygame.K_MINUS: lambda: self.change_speed(-1),
            pygame.K_KP_MINUS: lambda: self.change_speed(-1),
            pygame.K_DOWN: lambda: self.change_speed(-1),
        }
        if key == pygame.K_ESCAPE:
            if self.state == RUNNING:
                self.toggle_run()
        elif key in actions:
            self.run_action(actions[key])

    def _on_mouse_down(self, event):
        if event.button not in (1, 3):  # Ignore wheel and side buttons.
            return
        pos = event.pos

        if self.overlay:
            if event.button == 1 and (
                self.overlay_close.collidepoint(pos) or not self.overlay_card.collidepoint(pos)
            ):
                self.close_overlay()
            return

        if event.button == 1:
            for button in self.buttons:
                if button.contains(pos):
                    self.pressed_button = button
                    return
            if self.slider.contains(pos):
                self.slider.dragging = True
                self.set_speed(self.slider.value_at(pos[0]))
                return

        cell = self._cell_at(pos)
        if cell is not None:
            self.run_action(lambda: self._begin_edit(cell, event.button))

    def _on_mouse_up(self, event):
        if event.button == 1:
            button, self.pressed_button = self.pressed_button, None
            if button is not None and button.contains(event.pos):
                self.run_action(button.action)
            self.slider.dragging = False
        if event.button == self.edit_button:
            self._end_edit()

    def _on_mouse_move(self, event):
        if self.slider.dragging:
            self.set_speed(self.slider.value_at(event.pos[0]))
        elif self.edit_mode is not None:
            cell = self._cell_at(event.pos)
            if cell is not None:
                self.run_action(lambda: self._continue_edit(cell))

    # -------------------------------------------------------------- editing
    def _cell_at(self, pos):
        x, y = pos
        if not (GRID_X <= x < GRID_X + GRID_W and GRID_Y <= y < GRID_Y + GRID_H):
            return None
        return self.grid.get_cell((y - GRID_Y) // CELL, (x - GRID_X) // CELL)

    def _begin_edit(self, cell, mouse_button):
        grid = self.grid
        if mouse_button == 1 and cell is grid.start:
            mode = MOVE_START
        elif mouse_button == 1 and cell is grid.end:
            mode = MOVE_END
        elif not grid.is_interior(cell.row, cell.col):
            self.set_status("The outer border of the maze cannot be edited.")
            return
        elif mouse_button == 3:
            mode = ERASE
        elif pygame.key.get_mods() & pygame.KMOD_SHIFT:
            mode = REMOVE_WEIGHT if cell.weight > 1 else PAINT_WEIGHT
        else:
            mode = ERASE if cell.is_wall else DRAW_WALL

        self.edit_mode = mode
        self.edit_button = mouse_button
        self.last_edit_cell = cell
        self._apply_edit(cell)

    def _continue_edit(self, cell):
        if self.edit_mode in (MOVE_START, MOVE_END):
            self._apply_edit(cell)
            return
        last = self.last_edit_cell
        if last is None or cell is last:
            return
        for row, col in cells_between((last.row, last.col), (cell.row, cell.col)):
            target = self.grid.get_cell(row, col)
            if target is not None:
                self._apply_edit(target)
        self.last_edit_cell = cell

    def _end_edit(self):
        self.edit_mode = None
        self.edit_button = None
        self.last_edit_cell = None

    def _apply_edit(self, cell):
        grid = self.grid
        interior = grid.is_interior(cell.row, cell.col)

        if self.edit_mode == MOVE_START:
            if cell is not grid.start and interior and grid.set_start(cell):
                self._after_edit()
            return
        if self.edit_mode == MOVE_END:
            if cell is not grid.end and interior and grid.set_end(cell):
                self._after_edit()
            return

        if not interior or cell is grid.start or cell is grid.end:
            return

        changed = False
        if self.edit_mode == DRAW_WALL and not cell.is_wall:
            cell.is_wall, cell.weight = True, 1
            changed = True
        elif self.edit_mode == ERASE and (cell.is_wall or cell.weight > 1):
            cell.is_wall, cell.weight = False, 1
            changed = True
        elif self.edit_mode == PAINT_WEIGHT and not cell.is_wall and cell.weight == 1:
            cell.weight = DEFAULT_WEIGHT
            changed = True
        elif self.edit_mode == REMOVE_WEIGHT and cell.weight > 1:
            cell.weight = 1
            changed = True

        if changed:
            self._after_edit()

    def _after_edit(self):
        if self.state != IDLE:
            self.reset_search(quiet=True)
            self.set_status("The maze changed, so the previous search was cleared.")
        self._grid_changed()

    # -------------------------------------------------------------- drawing
    def draw(self):
        mouse = pygame.mouse.get_pos()
        self.screen.fill(Color.BG)
        self._draw_sidebar(mouse)
        self._draw_legend()
        self._draw_grid(mouse)
        self._draw_status_bar(mouse)
        if self.overlay == "help":
            self._draw_help(mouse)
        elif self.overlay == "compare":
            self._draw_compare(mouse)

    def _text(self, font, text, color, pos, anchor="topleft"):
        if not text:
            return pygame.Rect(pos, (0, 0))
        surface = self.texts.render(font, text, color)
        rect = surface.get_rect(**{anchor: pos})
        self.screen.blit(surface, rect)
        return rect

    def _section_header(self, text, y, right_text="", right_color=Color.MUTED):
        self._text(self.fonts.label, text.upper(), Color.DIM, (SIDE_PAD, y))
        if right_text:
            self._text(
                self.fonts.small_bold,
                right_text,
                right_color,
                (SIDE_PAD + CONTENT_W, y - 1),
                "topright",
            )

    def _draw_sidebar(self, mouse):
        screen = self.screen
        screen.fill(Color.SIDEBAR, (0, 0, SIDEBAR_W, SIDEBAR_H))
        screen.fill(Color.BORDER_SOFT, (SIDEBAR_W - 1, 0, 1, SIDEBAR_H))

        logo = pygame.Rect(SIDE_PAD, 24, 38, 38)
        draw_logo(screen, logo)
        self._text(
            self.fonts.title,
            "Theseus",
            Color.TEXT,
            (logo.right + 12, logo.centery + 3),
            "bottomleft",
        )
        self._text(
            self.fonts.small,
            "Graph Traversal Maze Solver",
            Color.MUTED,
            (logo.right + 12, logo.centery + 3),
            "topleft",
        )

        self._section_header("Algorithm", Y_ALGO_HEADER)
        for button in self.algo_buttons.values():
            self._draw_button(button, mouse)

        lines = wrap_text(self.fonts.small, self.info.description, CONTENT_W, max_lines=2)
        for index, line in enumerate(lines):
            self._text(self.fonts.small, line, Color.MUTED, (SIDE_PAD, Y_DESCRIPTION + index * 17))
        self._draw_tags(self.info.tags, SIDE_PAD, Y_TAGS)

        self._section_header("Controls", Y_CONTROLS_HEADER)
        for button in (
            self.solve_button,
            self.step_button,
            self.reset_button,
            self.compare_button,
            self.maze_button,
            self.weights_button,
            self.clear_button,
        ):
            self._draw_button(button, mouse)

        self._section_header("Speed", Y_SPEED_HEADER, self.speed_label(), Color.ACCENT_TEXT)
        self._draw_slider(mouse)

        self._section_header("Statistics", Y_STATS_HEADER)
        self._draw_stats()

    def _draw_tags(self, tags, x, y):
        for label, color in tags:
            surface = self.texts.render(self.fonts.label, label, color)
            rect = pygame.Rect(x, y, surface.get_width() + 18, 22)
            if rect.right > SIDE_PAD + CONTENT_W:
                break
            pygame.draw.rect(self.screen, mix(Color.SIDEBAR, color, 0.10), rect, border_radius=11)
            pygame.draw.rect(
                self.screen, mix(Color.SIDEBAR, color, 0.45), rect, width=1, border_radius=11
            )
            self.screen.blit(surface, surface.get_rect(center=rect.center))
            x = rect.right + 6

    def _draw_button(self, button, mouse):
        hovered = not self.overlay and button.contains(mouse)
        pressed = hovered and self.pressed_button is button
        rect = button.rect.move(0, 1) if pressed else button.rect

        if not button.enabled:
            background, foreground, border = Color.BUTTON_DISABLED, Color.DIM, Color.BORDER_SOFT
        elif button.primary:
            background = (
                Color.ACCENT_PRESSED
                if pressed
                else Color.ACCENT_HOVER
                if hovered
                else Color.ACCENT
            )
            foreground, border = Color.WHITE, None
        elif button.selected:
            background = Color.SELECTED_HOVER if hovered else Color.SELECTED
            foreground, border = Color.WHITE, Color.ACCENT
        else:
            background = Color.BUTTON_HOVER if hovered else Color.BUTTON
            foreground, border = Color.TEXT, Color.BORDER

        pygame.draw.rect(self.screen, background, rect, border_radius=8)
        if border:
            pygame.draw.rect(self.screen, border, rect, width=1, border_radius=8)

        font = self.fonts.button_bold if button.primary else self.fonts.button
        label = self.texts.render(font, button.label, foreground)
        icon_width = 16 if button.icon else 0
        left = rect.centerx - (icon_width + label.get_width()) // 2
        if button.icon:
            self._draw_icon(button.icon, left, rect.centery, foreground)
        self.screen.blit(label, label.get_rect(midleft=(left + icon_width, rect.centery)))

        if button.hotkey and button.enabled:
            hint_color = Color.ACCENT_TEXT if button.primary else Color.DIM
            self._text(
                self.fonts.small,
                button.hotkey,
                hint_color,
                (rect.right - 12, rect.centery),
                "midright",
            )

    def _draw_icon(self, icon, x, center_y, color):
        if icon == "play":
            pygame.draw.polygon(
                self.screen, color, [(x, center_y - 6), (x, center_y + 6), (x + 10, center_y)]
            )
        elif icon == "pause":
            self.screen.fill(color, (x, center_y - 6, 3, 12))
            self.screen.fill(color, (x + 6, center_y - 6, 3, 12))

    def _draw_slider(self, mouse):
        slider = self.slider
        center_y = slider.rect.centery
        track = pygame.Rect(slider.rect.left, center_y - 2, slider.rect.width, 4)
        pygame.draw.rect(self.screen, Color.BORDER, track, border_radius=2)
        handle_x = slider.handle_x()
        filled = pygame.Rect(slider.rect.left, center_y - 2, handle_x - slider.rect.left, 4)
        if filled.width > 0:
            pygame.draw.rect(self.screen, Color.ACCENT, filled, border_radius=2)

        active = slider.dragging or (not self.overlay and slider.contains(mouse))
        radius = 9 if active else 8
        pygame.draw.circle(
            self.screen,
            Color.ACCENT_HOVER if active else Color.ACCENT,
            (handle_x, center_y),
            radius,
        )
        pygame.draw.circle(self.screen, Color.WHITE, (handle_x, center_y), radius - 4)

    def _draw_stats(self):
        has_result = self.state == DONE
        no_path = has_result and not self.path
        explored = len(self.visited) / self.open_cells * 100 if self.open_cells else 0.0

        if has_result and self.path:
            length_value, length_color = f"{len(self.path) - 1:,}", Color.PATH
            cost_value, cost_color = f"{path_cost(self.path):,}", Color.PATH
        elif no_path:
            length_value, length_color = "None", Color.ERROR
            cost_value, cost_color = "None", Color.ERROR
        else:
            length_value, length_color = "—", Color.DIM
            cost_value, cost_color = "—", Color.DIM

        tiles = (
            ("Visited", f"{len(self.visited):,}", Color.TEXT),
            ("Frontier", f"{len(self.frontier):,}", Color.TEXT),
            ("Path length", length_value, length_color),
            ("Path cost", cost_value, cost_color),
            ("Explored", f"{explored:.0f}%", Color.TEXT),
            ("Compute time", f"{self.compute_time * 1000:.2f} ms", Color.TEXT),
        )
        half = (CONTENT_W - GAP) // 2
        for index, (label, value, color) in enumerate(tiles):
            col, row = index % 2, index // 2
            rect = pygame.Rect(
                SIDE_PAD + col * (half + GAP),
                Y_STATS + row * (TILE_H + TILE_GAP),
                half if col == 0 else CONTENT_W - half - GAP,
                TILE_H,
            )
            pygame.draw.rect(self.screen, Color.PANEL, rect, border_radius=8)
            pygame.draw.rect(self.screen, Color.BORDER_SOFT, rect, width=1, border_radius=8)
            self._text(self.fonts.label, label.upper(), Color.DIM, (rect.x + 10, rect.y + 5))
            value = fit_text(self.fonts.value, value, rect.width - 20)
            self._text(
                self.fonts.value, value, color, (rect.x + 10, rect.bottom - 3), "bottomleft"
            )

    def _state_label(self):
        if self.state == RUNNING:
            return "Running", Color.ACCENT_HOVER
        if self.state == PAUSED:
            return "Paused", Color.WARNING
        if self.state == DONE:
            return ("Path found", Color.SUCCESS) if self.path else ("No path", Color.ERROR)
        return "Ready", Color.MUTED

    def _draw_swatch(self, kind, rect):
        screen = self.screen
        fills = {
            "start": Color.START,
            "end": Color.END,
            "frontier": Color.FRONTIER,
            "visited": Color.VISITED,
            "path": Color.PATH,
            "wall": Color.WALL,
            "weight": Color.FLOOR,
        }
        pygame.draw.rect(screen, fills[kind], rect, border_radius=4)
        if kind == "wall":
            pygame.draw.rect(screen, Color.BORDER, rect, width=1, border_radius=4)
        elif kind == "weight":
            self._draw_weight_marker(rect, Color.WEIGHT)

    def _draw_legend(self):
        center_y = PAD + (LEGEND_H - 10) // 2
        x = GRID_X
        for label, kind in LEGEND:
            self._draw_swatch(kind, pygame.Rect(x, center_y - 7, 14, 14))
            text_rect = self._text(
                self.fonts.small, label, Color.MUTED, (x + 20, center_y), "midleft"
            )
            x = text_rect.right + 18

        label, color = self._state_label()
        text = self.texts.render(self.fonts.small_bold, f"{self.algorithm}  ·  {label}", color)
        chip = pygame.Rect(0, 0, text.get_width() + 34, 26)
        chip.midright = (GRID_X + GRID_W, center_y)
        if chip.left > x:
            pygame.draw.rect(self.screen, mix(Color.BG, color, 0.10), chip, border_radius=13)
            pygame.draw.rect(
                self.screen, mix(Color.BG, color, 0.40), chip, width=1, border_radius=13
            )
            pygame.draw.circle(self.screen, color, (chip.left + 14, chip.centery), 4)
            self.screen.blit(text, text.get_rect(midleft=(chip.left + 24, chip.centery)))

    def _draw_weight_marker(self, rect, color):
        cx, cy = rect.center
        r = max(3, rect.width // 4)
        pygame.draw.polygon(
            self.screen, color, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        )

    def _draw_grid(self, mouse):
        screen = self.screen
        area = pygame.Rect(GRID_X, GRID_Y, GRID_W, GRID_H)
        pygame.draw.rect(screen, Color.PANEL, area.inflate(14, 14), border_radius=10)
        pygame.draw.rect(
            screen, Color.BORDER_SOFT, area.inflate(14, 14), width=1, border_radius=10
        )
        screen.fill(Color.GRID_LINE, area)

        revealed = set(self.path[: int(self.reveal)]) if self.path else set()
        visited, frontier = self.visited, self.frontier
        for row in self.grid.cells:
            for cell in row:
                x = GRID_X + cell.col * CELL
                y = GRID_Y + cell.row * CELL
                if cell.is_wall:
                    screen.fill(Color.WALL, (x, y, CELL, CELL))
                    continue
                if cell in revealed:
                    color = Color.PATH
                elif cell in frontier:
                    color = Color.FRONTIER
                elif cell in visited:
                    color = Color.VISITED
                else:
                    color = Color.FLOOR
                inner = pygame.Rect(x + 1, y + 1, CELL - 1, CELL - 1)
                screen.fill(color, inner)
                if cell.weight > 1:
                    on_bright = color in (Color.PATH, Color.FRONTIER)
                    marker = Color.WEIGHT_ON_PATH if on_bright else Color.WEIGHT
                    self._draw_weight_marker(inner, marker)

        self._draw_endpoint(self.grid.start, Color.START, "S")
        self._draw_endpoint(self.grid.end, Color.END, "E")

        if not self.overlay and self.edit_mode is None:
            cell = self._cell_at(mouse)
            if cell is not None and (self.grid.is_interior(cell.row, cell.col)):
                rect = pygame.Rect(
                    GRID_X + cell.col * CELL, GRID_Y + cell.row * CELL, CELL + 1, CELL + 1
                )
                pygame.draw.rect(screen, Color.HOVER, rect, width=2, border_radius=3)

    def _draw_endpoint(self, cell, color, letter):
        rect = pygame.Rect(
            GRID_X + cell.col * CELL + 2, GRID_Y + cell.row * CELL + 2, CELL - 3, CELL - 3
        )
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        self._text(self.fonts.cell, letter, Color.WHITE, rect.center, "center")

    def _hover_description(self, mouse):
        cell = self._cell_at(mouse)
        if cell is None or self.overlay:
            return "Left drag: walls  ·  Right drag: erase  ·  Shift: weights  ·  H: help"
        if cell is self.grid.start:
            kind = "Start (drag to move)"
        elif cell is self.grid.end:
            kind = "End (drag to move)"
        elif cell.is_wall:
            kind = "Wall"
        elif cell.weight > 1:
            kind = f"Weighted cell, cost {cell.weight}"
        else:
            kind = "Open cell, cost 1"
        return f"Row {cell.row}, Col {cell.col}  ·  {kind}"

    def _draw_status_bar(self, mouse):
        top = HEIGHT - STATUS_H
        self.screen.fill(Color.SIDEBAR, (0, top, WIDTH, STATUS_H))
        self.screen.fill(Color.BORDER_SOFT, (0, top, WIDTH, 1))
        center_y = top + STATUS_H // 2

        hint = self._hover_description(mouse)
        hint_rect = self._text(
            self.fonts.small, hint, Color.DIM, (WIDTH - PAD, center_y), "midright"
        )

        color = STATUS_COLORS[self.status_level]
        pygame.draw.circle(self.screen, color, (SIDE_PAD, center_y), 4)
        text_color = Color.TEXT if self.status_level == "info" else color
        message = fit_text(
            self.fonts.small, self.status_text, hint_rect.left - (SIDE_PAD + 12) - 24
        )
        self._text(self.fonts.small, message, text_color, (SIDE_PAD + 12, center_y), "midleft")

    # ------------------------------------------------------------- overlays
    def _begin_overlay(self, width, height, title, subtitle, mouse):
        self.screen.blit(self.dim_layer, (0, 0))
        card = pygame.Rect(0, 0, width, height)
        card.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(self.screen, Color.PANEL, card, border_radius=14)
        pygame.draw.rect(self.screen, Color.BORDER, card, width=1, border_radius=14)
        self.overlay_card = card

        self._text(self.fonts.heading, title, Color.TEXT, (card.x + 28, card.y + 22))
        self._text(self.fonts.small, subtitle, Color.MUTED, (card.x + 28, card.y + 50))

        close = pygame.Rect(card.right - 48, card.y + 18, 30, 30)
        if close.collidepoint(mouse):
            pygame.draw.rect(self.screen, Color.BUTTON_HOVER, close, border_radius=8)
        cx, cy = close.center
        pygame.draw.line(self.screen, Color.MUTED, (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
        pygame.draw.line(self.screen, Color.MUTED, (cx - 5, cy + 5), (cx + 5, cy - 5), 2)
        self.overlay_close = close
        return card

    def _draw_keycap(self, text, x, center_y):
        surface = self.texts.render(self.fonts.small_bold, text, Color.TEXT)
        rect = pygame.Rect(x, center_y - 11, max(28, surface.get_width() + 16), 22)
        pygame.draw.rect(self.screen, Color.BUTTON, rect, border_radius=6)
        pygame.draw.rect(self.screen, Color.BORDER, rect, width=1, border_radius=6)
        self.screen.blit(surface, surface.get_rect(center=rect.center))
        return rect

    def _draw_help(self, mouse):
        card = self._begin_overlay(
            680,
            470,
            "Keyboard & mouse shortcuts",
            "Everything can be done with the buttons too.",
            mouse,
        )
        column_w = (card.width - 28 * 3) // 2
        left_x, right_x = card.x + 28, card.x + 28 * 2 + column_w
        top = card.y + 88

        self._text(self.fonts.label, "KEYBOARD", Color.DIM, (left_x, top))
        for index, (keys, description) in enumerate(HELP_KEYS):
            center_y = top + 32 + index * 27
            self._draw_keycap(keys, left_x, center_y)
            self._text(
                self.fonts.body, description, Color.TEXT, (left_x + 96, center_y), "midleft"
            )

        self._text(self.fonts.label, "MOUSE", Color.DIM, (right_x, top))
        for index, (action, description) in enumerate(HELP_MOUSE):
            center_y = top + 32 + index * 27
            self._draw_keycap(action, right_x, center_y)
            self._text(
                self.fonts.body, description, Color.TEXT, (right_x + 112, center_y), "midleft"
            )

        tips_y = top + 32 + len(HELP_MOUSE) * 27 + 16
        self._text(self.fonts.label, "TIP", Color.DIM, (right_x, tips_y))
        for index, line in enumerate(wrap_text(self.fonts.small, HELP_TIP, column_w)):
            self._text(self.fonts.small, line, Color.MUTED, (right_x, tips_y + 20 + index * 18))

        self._text(
            self.fonts.small,
            "Press Esc or click outside to close",
            Color.DIM,
            (card.centerx, card.bottom - 22),
            "center",
        )

    def _draw_compare(self, mouse):
        row_h = 36
        card = self._begin_overlay(
            620,
            174 + row_h * len(self.compare_results),
            "Algorithm comparison",
            "Every algorithm run on the current maze without animation.",
            mouse,
        )
        left, right = card.x + 28, card.right - 28
        columns = (
            ("Visited", right - 300),
            ("Path length", right - 200),
            ("Path cost", right - 100),
            ("Time", right),
        )
        header_y = card.y + 90

        self._text(self.fonts.label, "ALGORITHM", Color.DIM, (left, header_y))
        for title, x in columns:
            self._text(self.fonts.label, title.upper(), Color.DIM, (x, header_y), "topright")

        solved = [r for r in self.compare_results if r.error is None and r.cost is not None]
        valid = [r for r in self.compare_results if r.error is None]
        best_visited = min((r.visited for r in valid), default=None)
        best_length = min((r.length for r in solved), default=None)
        best_cost = min((r.cost for r in solved), default=None)

        def styled(value, best):
            return Color.SUCCESS if best is not None and value == best else Color.TEXT

        for index, result in enumerate(self.compare_results):
            row = pygame.Rect(
                card.x + 16, header_y + 22 + index * row_h, card.width - 32, row_h - 4
            )
            if index % 2 == 0:
                pygame.draw.rect(self.screen, Color.PANEL_ALT, row, border_radius=8)
            if result.name == self.algorithm:
                pygame.draw.rect(
                    self.screen,
                    Color.ACCENT,
                    (row.x, row.y + 6, 3, row.height - 12),
                    border_radius=2,
                )
            center_y = row.centery
            self._text(self.fonts.body_bold, result.name, Color.TEXT, (left, center_y), "midleft")

            if result.error is not None:
                message = fit_text(
                    self.fonts.small, f"Failed: {result.error}", right - (left + 120)
                )
                self._text(self.fonts.small, message, Color.ERROR, (right, center_y), "midright")
                continue

            cells = (
                (f"{result.visited:,}", styled(result.visited, best_visited)),
                ("No path", Color.ERROR)
                if result.length is None
                else (f"{result.length:,}", styled(result.length, best_length)),
                ("—", Color.DIM)
                if result.cost is None
                else (f"{result.cost:,}", styled(result.cost, best_cost)),
                (f"{result.millis:.2f} ms", Color.MUTED),
            )
            for (value, color), (_, x) in zip(cells, columns):
                self._text(self.fonts.body, value, color, (x, center_y), "midright")

        self._text(
            self.fonts.small,
            "Green marks the best value in each column. BFS and DFS ignore weights.",
            Color.DIM,
            (card.centerx, card.bottom - 24),
            "center",
        )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def enable_high_dpi():
    """Ask Windows not to blur the window on scaled displays."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def create_window():
    if pygame.version.vernum < (2, 0):
        raise RuntimeError(
            f"pygame 2.0 or newer is required (found {pygame.version.ver}). "
            "Upgrade with:  python -m pip install --upgrade pygame-ce"
        )
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption(TITLE)
    try:
        pygame.display.set_icon(make_window_icon())
    except pygame.error:
        log.debug("Window icon not supported on this platform.")

    try:
        return pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
    except pygame.error:
        log.info("Scaled window unavailable, falling back to a fixed-size window.")
        return pygame.display.set_mode((WIDTH, HEIGHT))


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    enable_high_dpi()
    try:
        screen = create_window()
    except (pygame.error, RuntimeError) as error:
        log.error("Could not open the Theseus window: %s", error)
        pygame.quit()
        return 1

    try:
        App(screen).run()
    except KeyboardInterrupt:
        pass
    except Exception:
        log.exception("Theseus stopped because of an unexpected error.")
        return 1
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
