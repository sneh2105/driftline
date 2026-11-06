"""Approval Health scoring. Pure functions, no DB, so it's easy to test.

An "event" is a dict with: approver, risk (int 0-3), seconds (decision time),
decision ('approve'|'reject'), ts (epoch seconds).
"""
from __future__ import annotations

import statistics
from collections import defaultdict

RISK_LEVELS = ["low", "medium", "high", "critical"]
RISK_RANK = {name: i for i, name in enumerate(RISK_LEVELS)}

# Tunables. Surfaced in /v1/config so the UI can explain flags.
CONFIG = {
    "healthy_median_seconds": 30.0,   # median review time we consider "real reading"
    "rubber_stamp_seconds": 5.0,      # median below this = flag
    "healthy_reject_rate": 0.05,      # ~5% rejects = control is doing something
    "min_events_speed": 20,
    "min_events_zero_reject": 50,
    "min_events_risk": 30,
    "high_risk_fast_seconds": 3.0,
    "min_events_high_risk_fast": 10,
    "risk_blind_corr": 0.1,
    "drift_ratio": 0.5,               # last-7d median < 50% of earlier median
    "drift_window_days": 7,
    "min_events_drift_recent": 10,
    "min_events_drift_older": 20,
    "healthy_risk_corr": 0.4,
    "score_healthy": 70,
    "score_watch": 40,
}


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def _ranks(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def risk_sensitivity(events: list[dict]) -> float | None:
    """Spearman correlation between risk level and decision time.
    A real reviewer takes longer on riskier actions -> positive."""
    if len(events) < 3:
        return None
    risks = [float(e["risk"]) for e in events]
    secs = [float(e["seconds"]) for e in events]
    return _corr(_ranks(risks), _ranks(secs))


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def label_for(score: float) -> str:
    if score >= CONFIG["score_healthy"]:
        return "healthy"
    if score >= CONFIG["score_watch"]:
        return "watch"
    return "rubber_stamp"


def score_events(events: list[dict], now: float | None = None) -> dict:
    """Score a set of events for one approver (or the whole org)."""
    n = len(events)
    if n == 0:
        return {"n": 0, "score": None, "label": "no_data", "flags": []}

    secs = [e["seconds"] for e in events]
    median_s = statistics.median(secs)
    rejects = sum(1 for e in events if e["decision"] == "reject")
    reject_rate = rejects / n
    corr = risk_sensitivity(events)

    speed = _clamp(median_s / CONFIG["healthy_median_seconds"]) * 40
    reject = _clamp(reject_rate / CONFIG["healthy_reject_rate"]) * 30
    if corr is None:
        sens = 15.0  # unknown -> neutral, don't punish or reward
    else:
        sens = _clamp(corr / CONFIG["healthy_risk_corr"]) * 30
    score = round(speed + reject + sens, 1)

    by_risk = defaultdict(list)
    for e in events:
        by_risk[e["risk"]].append(e["seconds"])
    median_by_risk = {RISK_LEVELS[r]: round(statistics.median(v), 2) for r, v in sorted(by_risk.items())}

    flags = _flags(events, median_s, reject_rate, corr, by_risk, now)

    return {
        "n": n,
        "score": score,
        "label": label_for(score),
        "median_seconds": round(median_s, 2),
        "p90_seconds": round(_percentile(secs, 90), 2),
        "reject_rate": round(reject_rate, 4),
        "rejects": rejects,
        "risk_sensitivity": None if corr is None else round(corr, 3),
        "median_by_risk": median_by_risk,
        "components": {"speed": round(speed, 1), "rejects": round(reject, 1), "risk_sensitivity": round(sens, 1)},
        "flags": flags,
    }


def _percentile(vals: list[float], p: float) -> float:
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def _flags(events, median_s, reject_rate, corr, by_risk, now) -> list[dict]:
    n = len(events)
    flags: list[dict] = []

    if n >= CONFIG["min_events_speed"] and median_s < CONFIG["rubber_stamp_seconds"]:
        flags.append({
            "code": "fast_median", "severity": "high",
            "title": "Decisions are too fast to be real reviews",
            "detail": f"Median decision time is {median_s:.1f}s across {n} actions "
                      f"(under {CONFIG['rubber_stamp_seconds']:.0f}s).",
        })

    if n >= CONFIG["min_events_zero_reject"] and reject_rate == 0:
        flags.append({
            "code": "zero_rejects", "severity": "high",
            "title": "Nothing rejected",
            "detail": f"{n} actions reviewed, 0 rejected. Either the agent is perfect or the gate isn't doing anything.",
        })

    hi = [s for r, v in by_risk.items() if r >= 2 for s in v]
    if len(hi) >= CONFIG["min_events_high_risk_fast"] and statistics.median(hi) < CONFIG["high_risk_fast_seconds"]:
        flags.append({
            "code": "high_risk_fast", "severity": "high",
            "title": "High-risk actions approved in seconds",
            "detail": f"Median {statistics.median(hi):.1f}s on {len(hi)} high/critical actions.",
        })

    if n >= CONFIG["min_events_risk"] and len(by_risk) >= 2 and corr is not None and corr < CONFIG["risk_blind_corr"]:
        flags.append({
            "code": "risk_blind", "severity": "medium",
            "title": "Review time ignores risk",
            "detail": f"Risk/time correlation is {corr:.2f}. Wires and routine replies get the same attention.",
        })

    if now is not None:
        cutoff = now - CONFIG["drift_window_days"] * 86400
        recent = [e["seconds"] for e in events if e["ts"] >= cutoff]
        older = [e["seconds"] for e in events if e["ts"] < cutoff]
        if len(recent) >= CONFIG["min_events_drift_recent"] and len(older) >= CONFIG["min_events_drift_older"]:
            r_med, o_med = statistics.median(recent), statistics.median(older)
            if o_med > 0 and r_med < o_med * CONFIG["drift_ratio"]:
                flags.append({
                    "code": "speed_drift", "severity": "medium",
                    "title": "Getting faster over time",
                    "detail": f"Last 7 days median {r_med:.1f}s vs {o_med:.1f}s before. Classic fatigue curve.",
                })
    return flags


def daily_trend(events: list[dict], now: float, days: int = 30, window: int = 7) -> list[dict]:
    """Rolling `window`-day score ending on each of the last `days` days."""
    out = []
    day = 86400
    for i in range(days - 1, -1, -1):
        end = now - i * day
        start = end - window * day
        win = [e for e in events if start < e["ts"] <= end]
        if len(win) < 5:
            out.append({"ts": end, "score": None, "n": len(win)})
            continue
        s = score_events(win)
        out.append({"ts": end, "score": s["score"], "n": len(win),
                    "median_seconds": s["median_seconds"], "reject_rate": s["reject_rate"]})
    return out
