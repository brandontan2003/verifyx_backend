from enum import Enum


class ReactionType(str, Enum):
    UP_VOTE = "up_vote"
    DOWN_VOTE = "down_vote"
