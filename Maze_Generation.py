import random
def maze_generation(grid,EXTRA=0.08):
    for cell in grid.get_all():
        cell.is_wall=True
        cell.weight=1



    first =grid.get_one(1,1)
    first.is_wall=False
    stack=[first]
    seen={first}

    while stack:
        cur=stack[-1]
        options=[]
        for dx,dy in ((-2,0),(2,0),(0,2),(0,-2)):
            nc=grid.get_one(cur.row+dx,cur.col+dy)
            if nc is not None and nc not in seen and 0<nc<grid.row-1 and 0<nc.col<grid.col-1:
                options.append(nc)


        if not options:
            stack.pop()
            continue

        nxt=random.choice(options)
        btw=grid.get_one((nxt.row+cur.row)//2,(nxt.col+cur.col)//2)
        btw.is_wall=False
        nxt.is_wall=False
        seen.add(nxt)
        stack.append(nxt)


    for cell in grid.get_all():
        ok=0<cell.row<grid.row-1 and 0<cell.col<grid.col-1
        if cell.is_wall and ok and random.random()<EXTRA:
            cell.is_wall=True

    grid.start=grid.get_one(1,1)
    grid.end=grid.get_one(grid.row-2,grid.col-2)
    grid.start.is_wall=False
    grid.end.is_wall=False


def add_random_weights(grid,chance=.15,weight=15):
    for cell in grid.get_all():
        if cell.is_wall or cell is grid.start or cell is grid.end:
            continue
        if random.random()<chance:
            cell.weight=weight
