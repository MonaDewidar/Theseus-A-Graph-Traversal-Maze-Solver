"""Grid model used by the maze generator, the search algorithms and the GUI."""

MIN_SIZE = 5
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Cell:
    """A single square of the maze."""

    __slots__ = ("row", "col", "is_wall", "weight")

    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.is_wall = False
        self.weight = 1

    def __repr__(self):
        kind = "wall" if self.is_wall else f"weight={self.weight}"
        return f"Cell({self.row}, {self.col}, {kind})"


class Grid:
    """A rectangular grid of cells with a start and an end cell."""

    def __init__(self, rows, cols):
        if not isinstance(rows, int) or not isinstance(cols, int):
            raise TypeError("rows and cols must be integers")
        if rows < MIN_SIZE or cols < MIN_SIZE:
            raise ValueError(f"grid must be at least {MIN_SIZE}x{MIN_SIZE}, got {rows}x{cols}")

        self.rows = rows
        self.cols = cols
        self.cells = [[Cell(row, col) for col in range(cols)] for row in range(rows)]
        self.start = self.cells[1][1]
        self.end = self.cells[rows - 2][cols - 2]

    def is_valid(self, row, col):
        """Return True if (row, col) lies inside the grid."""
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_interior(self, row, col):
        """Return True if (row, col) is inside the grid and not on its border."""
        return 0 < row < self.rows - 1 and 0 < col < self.cols - 1

    def get_cell(self, row, col):
        """Return the cell at (row, col), or None if it is out of bounds."""
        if self.is_valid(row, col):
            return self.cells[row][col]
        return None

    def get_neighbors(self, cell):
        """Return the walkable cells directly above, below, left and right of cell."""
        neighbors = []
        for d_row, d_col in DIRECTIONS:
            row, col = cell.row + d_row, cell.col + d_col
            if self.is_valid(row, col) and not self.cells[row][col].is_wall:
                neighbors.append(self.cells[row][col])
        return neighbors

    def get_all(self):
        """Yield every cell, row by row."""
        for row in self.cells:
            yield from row

    def set_start(self, cell):
        """Move the start to cell. Returns False if the move is not allowed."""
        if cell is None or cell.is_wall or cell is self.end:
            return False
        self.start = cell
        return True

    def set_end(self, cell):
        """Move the end to cell. Returns False if the move is not allowed."""
        if cell is None or cell.is_wall or cell is self.start:
            return False
        self.end = cell
        return True

    def clear(self):
        """Remove every wall and weight, leaving an open board with a solid border."""
        for cell in self.get_all():
            cell.is_wall = not self.is_interior(cell.row, cell.col)
            cell.weight = 1
        self.start.is_wall = False
        self.end.is_wall = False

    def has_weights(self):
        """Return True if any cell costs more than 1 to enter."""
        return any(cell.weight > 1 for cell in self.get_all())
