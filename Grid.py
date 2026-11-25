class Cell:
    def __init__(self,row,col):
        self.row=row
        self.col=col
        self.is_wall=False
        self.weight=1

class Grid:
    def __init__(self,rows,cols):
        self.rows =rows
        self.cols =cols
        self.cells=[[Cell(row,col) for col in range(cols)] for row in range(rows)]
        self.start=self.cells[1][1]
        self.end  =self.cells[rows-2][cols-2]

    def vaid(self,row,col):
        return row>=0 and col>=0 and row<self.rows and col<self.cols
    
    def get_all_neigbors(self,row,col):
        all=[]
        for ni,nj in ((1,0),(-1,0),(0,1),(0,-1)):
            nrow=ni+row
            ncol=nj+col
            if valid(nrow,ncol) and self.cells[nrow][ncol].is_wall==False:
                all.append(self.cells[nrow][ncol])


    def get_one(self,row,col):
        if valid(row,col):
            return self.cells[row][col]

        return None

    def get_all(self):
        for row in self.cells:
            for cell in row:
                yield cell
                


