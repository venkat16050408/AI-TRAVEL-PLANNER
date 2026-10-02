"""2-constraint 0/1 Knapsack (budget + time)."""

from typing import List, Dict, Any


def knapsack_select(
    places: List[Dict[str, Any]],
    budget: float,
    time_slots: int,
    slot_size: int = 30,
    money_step: int = 100,
) -> List[Dict[str, Any]]:
    """Select places maximizing total value subject to budget (INR) and time (minutes).

    dp[i][b][t] = max(dp[i-1][b][t], dp[i-1][b-cost][t-time] + value)

    money_step quantises the budget axis so the DP table stays bounded;
    100 INR keeps stop costs (entry + food + transport reserve) meaningful.
    """
    n = len(places)
    B = min(int(budget // money_step), 600)   # cap DP table size for huge budgets
    T = min(int(time_slots), 400)
    if n == 0 or B <= 0 or T <= 0:
        return []

    costs = [max(0, int(round(float(p.get("cost", 0)) / money_step))) for p in places]
    times = [max(1, int(round(float(p.get("duration_minutes", 60)) / slot_size))) for p in places]
    values = [int(p.get("value", 1)) for p in places]

    # dp as (dp value, chosen set) for reconstruction simplicity at moderate N.
    dp = [[[0] * (T + 1) for _ in range(B + 1)] for _ in range(n + 1)]
    take = [[[False] * (T + 1) for _ in range(B + 1)] for _ in range(n + 1)]

    for i in range(1, n + 1):
        c, t, v = costs[i - 1], times[i - 1], values[i - 1]
        for b in range(B + 1):
            for tt in range(T + 1):
                best = dp[i - 1][b][tt]
                if c <= b and t <= tt and dp[i - 1][b - c][tt - t] + v > best:
                    best = dp[i - 1][b - c][tt - t] + v
                    take[i][b][tt] = True
                dp[i][b][tt] = best

    # Reconstruct
    selected = []
    b, tt = B, T
    for i in range(n, 0, -1):
        if take[i][b][tt]:
            selected.append(places[i - 1])
            b -= costs[i - 1]
            tt -= times[i - 1]
    selected.reverse()
    return selected
