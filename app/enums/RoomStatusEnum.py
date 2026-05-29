import enum


class RoomStatus(str, enum.Enum):
    waiting = "waiting"  # created, waiting for players
    active = "active"  # challenge in progress
    finished = "finished"  # all players submitted or time expired
