"""Random maze generation and weight placement."""

import random

DEFAULT_WEIGHT = 15


def _last_odd_index(size):
    """Largest odd index that is not on the border (carving only happens on odd cells)."""
    index = size - 2
    return index if index % 2 == 1 else index - 1


def maze_generation(grid, extra=0.08):
    """Carve a perfect maze with an iterative depth-first backtracker.

    After carving, a fraction ``extra`` of the walls that separate two corridors
    is knocked down so the maze contains loops and has more than one route.
    """
    if not 0.0 <= extra <= 1.0:
        raise ValueError(f"extra must be between 0 and 1, got {extra}")

    for cell in grid.get_all():
        cell.is_wall = True
        cell.weight = 1

    first = grid.get_cell(1, 1)
    first.is_wall = False
    stack = [first]
    seen = {first}

    while stack:
        current = stack[-1]
        options = []
        for d_row, d_col in ((-2, 0), (2, 0), (0, 2), (0, -2)):
            candidate = grid.get_cell(current.row + d_row, current.col + d_col)
            if (
                candidate is not None
                and candidate not in seen
                and grid.is_interior(candidate.row, candidate.col)
            ):
                options.append(candidate)

        if not options:
            stack.pop()
            continue

        chosen = random.choice(options)
        between = grid.get_cell((chosen.row + current.row) // 2, (chosen.col + current.col) // 2)
        between.is_wall = False
        chosen.is_wall = False
        seen.add(chosen)
        stack.append(chosen)

    _add_loops(grid, extra)

    grid.start = grid.get_cell(1, 1)
    grid.end = grid.get_cell(_last_odd_index(grid.rows), _last_odd_index(grid.cols))
    grid.start.is_wall = False
    grid.end.is_wall = False


def _add_loops(grid, chance):
    """Open walls that sit between two corridors, creating alternative routes."""
    if chance <= 0:
        return

    for cell in grid.get_all():
        if not cell.is_wall or not grid.is_interior(cell.row, cell.col):
            continue
        up = grid.cells[cell.row - 1][cell.col]
        down = grid.cells[cell.row + 1][cell.col]
        left = grid.cells[cell.row][cell.col - 1]
        right = grid.cells[cell.row][cell.col + 1]
        vertical = not up.is_wall and not down.is_wall
        horizontal = not left.is_wall and not right.is_wall
        if (vertical != horizontal) and random.random() < chance:
            cell.is_wall = False


def add_random_weights(grid, chance=0.15, weight=DEFAULT_WEIGHT):
    """Give a random selection of open cells a higher cost to enter."""
    if not 0.0 <= chance <= 1.0:
        raise ValueError(f"chance must be between 0 and 1, got {chance}")
    if weight < 1:
        raise ValueError(f"weight must be at least 1, got {weight}")

    for cell in grid.get_all():
        if cell.is_wall or cell is grid.start or cell is grid.end:
            continue
        if random.random() < chance:
            cell.weight = weight


def clear_weights(grid):
    """Reset every cell back to the default cost of 1."""
    for cell in grid.get_all():
        cell.weight = 1
