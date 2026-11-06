"""Seed demo data: 60 days of approvals for a fictional fintech with 6 approvers.

    python seed.py            # creates project 'Acme Pay (demo)' with key dl_demo_key
    python seed.py --reset    # wipe the db first
"""
import argparse
import math
import os
import random
import time

from server import db

DEMO_KEY = "dl_demo_key"

ACTIONS = {
    0: ["send_status_email", "update_ticket", "reply_to_customer"],
    1: ["refund_under_100", "update_crm_record", "export_report"],
    2: ["refund_over_1000", "change_payout_account", "bulk_email"],
    3: ["wire_transfer", "delete_customer_data", "deploy_to_prod"],
}
RISK_MIX = [0.45, 0.30, 0.17, 0.08]


def lognorm(rng, median, sigma=0.6):
    return max(0.4, rng.lognormvariate(math.log(median), sigma))


def profile(name, day_ago):
    """-> (median seconds by risk, reject prob, risk-sensitivity multiplier, per-day volume)"""
    healthy = ([8, 20, 45, 90], 0.08)
    if name == "maria":      # solid all along
        return healthy[0], 0.11, 16
    if name == "tom":        # fine, slightly low reject rate
        return [6, 14, 30, 60], 0.09, 14
    if name == "priya":      # reads everything the same, medium speed, ignores risk
        return [18, 18, 19, 19], 0.08, 12
    if name == "dev":        # was great, fatigue sets in ~3 weeks ago
        if day_ago > 24:
            return healthy[0], 0.09, 12
        t = max(0.0, min(1.0, (24 - day_ago) / 20))   # 0 -> 1 over 20 days
        base = [8, 20, 45, 90]
        fast = [1.6, 1.7, 1.8, 2.0]
        meds = [b * (1 - t) + f * t for b, f in zip(base, fast)]
        return meds, 0.09 * (1 - t), int(12 + 28 * t)
    if name == "alex":       # never rejected anything, always fast
        return [2.2, 2.4, 2.8, 3.0], 0.0, 40
    if name == "sam":        # new hire, fast but not insane, some rejects
        return [5, 9, 16, 28], 0.09, 10
    raise KeyError(name)


APPROVERS = {
    "maria@acmepay.com": "maria", "tom@acmepay.com": "tom", "priya@acmepay.com": "priya",
    "dev@acmepay.com": "dev", "alex@acmepay.com": "alex", "sam@acmepay.com": "sam",
}
AGENTS = ["support-agent", "payments-agent", "ops-agent"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--days", type=int, default=60)
    a = ap.parse_args()

    if a.reset and os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init()
    rng = random.Random(7)

    with db.conn() as c:
        row = db.project_for_key(DEMO_KEY)
        if row:
            pid = row["id"]
            c.execute("DELETE FROM approvals WHERE project_id=?", (pid,))
        else:
            pid = db.create_project("Acme Pay (demo)", DEMO_KEY)["id"]

        now = time.time()
        rows = []
        for email, key in APPROVERS.items():
            for day_ago in range(a.days, -1, -1):
                meds, rej_p, vol = profile(key, day_ago)
                day_start = now - day_ago * 86400
                # weekdays only, mostly
                wd = time.gmtime(day_start).tm_wday
                if wd >= 5 and rng.random() < 0.8:
                    continue
                n = max(0, int(rng.gauss(vol, vol * 0.2)))
                for _ in range(n):
                    risk = rng.choices(range(4), RISK_MIX)[0]
                    secs = lognorm(rng, meds[risk])
                    decided = day_start - rng.uniform(0, 8 * 3600)
                    if day_ago == 0 and decided > now:
                        continue
                    amount = None
                    if risk == 3 and rng.random() < 0.6:
                        amount = round(rng.uniform(5_000, 120_000), 2)
                    # risky stuff gets rejected a bit more often
                    p = rej_p * (0.7 + 0.2 * risk)
                    decision = "reject" if rng.random() < p else "approve"
                    rows.append((pid, None, email, rng.choice(AGENTS), rng.choice(ACTIONS[risk]), risk,
                                 amount, decision, decided - secs, decided, secs, None))
        c.executemany(
            """INSERT INTO approvals(project_id,event_id,approver,agent,action,risk,amount,decision,
               shown_at,decided_at,seconds,meta) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    print(f"seeded {len(rows)} approvals. api key: {DEMO_KEY}")


if __name__ == "__main__":
    main()
