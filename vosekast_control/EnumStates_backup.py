from enum import Enum


class States(Enum):
    PAUSE = 0
    RUNNING = 1
    READY = 2
    STOPPED = 3
    NONE = 4
    OPEN = 5
    CLOSED = 6
    INITED = 7
    PREPARING_MEASUREMENT = 8
    MEASURING = 9
    

