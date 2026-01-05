import math
from datetime import datetime


# absolute day difference
def _days(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 86400.0


# classic exponential decay per 30 days
def tdecay(ts: datetime, now: datetime, lam_month: float) -> float:
    return math.exp(-lam_month * (_days(ts, now) / 30.0))
