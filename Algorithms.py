"""Step-by-step path-finding algorithms.

Every algorithm is a generator with the signature ``algorithm(grid, visited, frontier)``.
It updates the ``visited`` and ``frontier`` sets in place and yields once per
expanded cell, so a caller can animate the search. When the search finishes the
generator returns the path from start to end (an empty list if none exists),
available as ``StopIteration.value``.
"""

import heapq
from collections import deque
from itertools import count


def build_path(parents, end):
    """Walk the parent links back from end and return the path start -> end."""
    if end not in parents:
        return []
    path = []
    cell = end
    while cell is not None:
        path.append(cell)
        cell = parents[cell]
    path.reverse()
    return path


def bfs(grid, visited, frontier):
    """Breadth-first search: shortest path by number of steps (ignores weights)."""
    start, end = grid.start, grid.end
    queue = deque([start])
    parents = {start: None}
    frontier.add(start)

    while queue:
        current = queue.popleft()
        frontier.discard(current)
        visited.add(current)

        if current is end:
            break

        for neighbor in grid.get_neighbors(current):
            if neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)
                frontier.add(neighbor)

        yield

    return build_path(parents, end)


def dfs(grid, visited, frontier):
    """Depth-first search: finds a path quickly, but not necessarily the shortest."""
    start, end = grid.start, grid.end
    stack = [(start, None)]
    parents = {}
    frontier.add(start)

    while stack:
        current, parent = stack.pop()
        if current in visited:
            continue

        parents[current] = parent
        frontier.discard(current)
        visited.add(current)

        if current is end:
            break

        for neighbor in grid.get_neighbors(current):
            if neighbor not in visited:
                stack.append((neighbor, current))
                frontier.add(neighbor)

        yield

    return build_path(parents, end)


def dijkstra(grid, visited, frontier):
    """Dijkstra's algorithm: lowest-cost path on weighted grids."""
    start, end = grid.start, grid.end
    tie_breaker = count()
    distance = {start: 0}
    parents = {start: None}
    heap = [(0, next(tie_breaker), start)]
    frontier.add(start)

    while heap:
        cost, _, current = heapq.heappop(heap)
        if current in visited or cost > distance[current]:
            continue

        frontier.discard(current)
        visited.add(current)

        if current is end:
            break

        for neighbor in grid.get_neighbors(current):
            new_cost = cost + neighbor.weight
            if neighbor not in distance or new_cost < distance[neighbor]:
                distance[neighbor] = new_cost
                parents[neighbor] = current
                heapq.heappush(heap, (new_cost, next(tie_breaker), neighbor))
                frontier.add(neighbor)

        yield

    return build_path(parents, end)


def a_star(grid, visited, frontier):
    """A* search: Dijkstra guided by the Manhattan distance to the end."""
    start, end = grid.start, grid.end
    tie_breaker = count()

    def heuristic(cell):
        return abs(cell.row - end.row) + abs(cell.col - end.col)

    # Heap entries are (f, h, order, cell): ties on f favour cells closer to the end.
    cost_so_far = {start: 0}
    parents = {start: None}
    heap = [(heuristic(start), heuristic(start), next(tie_breaker), start)]
    frontier.add(start)

    while heap:
        priority, distance_left, _, current = heapq.heappop(heap)
        cost = priority - distance_left
        if current in visited or cost > cost_so_far[current]:
            continue

        frontier.discard(current)
        visited.add(current)

        if current is end:
            break

        for neighbor in grid.get_neighbors(current):
            new_cost = cost + neighbor.weight
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                parents[neighbor] = current
                distance_left = heuristic(neighbor)
                heapq.heappush(
                    heap,
                    (new_cost + distance_left, distance_left, next(tie_breaker), neighbor),
                )
                frontier.add(neighbor)

        yield

    return build_path(parents, end)


def path_cost(path):
    """Total cost of walking the path (the start cell itself is free)."""
    return sum(cell.weight for cell in path[1:])


ALGORITHMS = {
    "BFS": bfs,
    "DFS": dfs,
    "Dijkstra": dijkstra,
    "A*": a_star,
}
