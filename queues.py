import collections

import heapq

class Queue:
    def __init__(self):
        self.elements = collections.deque()

    def empty(self):
        return len(self.elements) == 0

    def put(self, x):
        self.elements.append(x)

    def get(self):
        return self.elements.popleft()

class PriorityQueue:
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))

    def getLen(self):
        return len(self.elements)

    def removeLowestPriority(self):
        self.elements.remove(heapq.nsmallest(1, self.elements)[0])

    def get(self):
        return heapq.heappop(self.elements)[1]
