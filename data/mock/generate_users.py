"""
Mock User Population Generator

Generates 50K eligible loan product users with realistic distributions:
- Credit tiers: Prime (680+), Near-Prime (620-679), Recovering (580-619)
- Income: $55K-$115K partitioned by HCOL/MCOL/LCOL
- Demographics for fair lending monitoring
- Digital engagement signals
- Pre-experiment behavior (baseline adoption propensity)

Recovering customers have slightly higher baseline adoption — they're actively
working on credit and debt consolidation products are genuinely useful.
"""

import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from config.project_config import TOTAL_ELIGIBLE_USERS, RANDOM_SEED

np.random.seed(RANDOM_SEED)

CREDIT_TIERS = {
    "Prime": {"range": (680, 800), "share": 0.45},
    "Near-Prime": {"range": (620, 679), "share": 0.35},
    "Recovering": {"range": (580, 619), "share": 0.20},
}

COL_TIERS = {
    "HCOL": {"share": 0.30, "income_range": (75000, 115000)},
    "MCOL": {"share": 0.45, "income_range": (55000, 85000)},
    "LCOL": {"share": 0.25, "income_range": (55000, 70000)},
}

AGE_BRACKETS = {
    "22-30": 0.18,
    "31-40": 0.30,
    "41-50": 0.25,
    "51-60": 0.18,
    "61+": 0.09,
}

REGIONS = {
    "Northeast": 0.20,
    "Southeast": 0.22,
    "Midwest": 0.23,
    "Southwest": 0.17,
    "West": 0.18,
}

BASELINE_ADOPTION_BY_TIER = {
    "Prime": 0.030,
    "Near-Prime": 0.032,
    "Recovering": 0.038,
}


def generate_population(n=TOTAL_ELIGIBLE_USERS):
    users = pd.DataFrame({
        "user_id": [f"USR_{i:06d}" for i in range(1, n + 1)],
    })

    credit_tiers = []
    credit_scores = []
    for _ in range(n):
        tier = np.random.choice(
            list(CREDIT_TIERS.keys()),
            p=[v["share"] for v in CREDIT_TIERS.values()]
        )
        score = np.random.randint(
            CREDIT_TIERS[tier]["range"][0],
            CREDIT_TIERS[tier]["range"][1] + 1
        )
        credit_tiers.append(tier)
        credit_scores.append(score)

    users["credit_tier"] = credit_tiers
    users["credit_score"] = credit_scores

    col_assignments = np.random.choice(
        list(COL_TIERS.keys()),
        size=n,
        p=[v["share"] for v in COL_TIERS.values()]
    )
    users["col_tier"] = col_assignments

    incomes = []
    for col in col_assignments:
        low, high = COL_TIERS[col]["income_range"]
        income = int(np.random.normal(
            loc=(low + high) / 2,
            scale=(high - low) / 6
        ))
        income = max(low, min(high, income))
        incomes.append(income)
    users["annual_income"] = incomes

    users["age_bracket"] = np.random.choice(
        list(AGE_BRACKETS.keys()),
        size=n,
        p=list(AGE_BRACKETS.values())
    )

    users["gender"] = np.random.choice(
        ["M", "F", "Non-Binary", "Undisclosed"],
        size=n,
        p=[0.48, 0.46, 0.03, 0.03]
    )

    users["ethnicity"] = np.random.choice(
        ["White", "Black", "Hispanic", "Asian", "Other", "Undisclosed"],
        size=n,
        p=[0.42, 0.15, 0.20, 0.10, 0.05, 0.08]
    )

    users["region"] = np.random.choice(
        list(REGIONS.keys()),
        size=n,
        p=list(REGIONS.values())
    )

    users["account_tenure_months"] = np.random.randint(6, 120, size=n)

    users["debt_to_income"] = np.round(
        np.random.beta(2, 5, size=n) * 0.6, 3
    )

    app_usage = []
    for tier in users["credit_tier"]:
        if tier == "Recovering":
            app_usage.append(np.random.choice(
                ["daily", "weekly", "monthly", "rare"],
                p=[0.30, 0.35, 0.25, 0.10]
            ))
        elif tier == "Prime":
            app_usage.append(np.random.choice(
                ["daily", "weekly", "monthly", "rare"],
                p=[0.15, 0.30, 0.35, 0.20]
            ))
        else:
            app_usage.append(np.random.choice(
                ["daily", "weekly", "monthly", "rare"],
                p=[0.20, 0.30, 0.30, 0.20]
            ))
    users["app_usage_frequency"] = app_usage

    users["days_since_last_login"] = np.where(
        users["app_usage_frequency"] == "daily",
        np.random.randint(0, 3, size=n),
        np.where(
            users["app_usage_frequency"] == "weekly",
            np.random.randint(1, 8, size=n),
            np.where(
                users["app_usage_frequency"] == "monthly",
                np.random.randint(7, 35, size=n),
                np.random.randint(30, 120, size=n)
            )
        )
    )

    users["existing_products"] = np.random.randint(1, 5, size=n)

    baseline_propensity = []
    for _, row in users.iterrows():
        base = BASELINE_ADOPTION_BY_TIER[row["credit_tier"]]

        if row["app_usage_frequency"] == "daily":
            base *= 1.3
        elif row["app_usage_frequency"] == "rare":
            base *= 0.7

        if row["account_tenure_months"] > 60:
            base *= 1.1

        if row["debt_to_income"] > 0.3:
            base *= 1.15

        baseline_propensity.append(round(base, 5))

    users["baseline_propensity"] = baseline_propensity

    return users


def summarize_population(users):
    print(f"Total eligible users: {len(users):,}")

    print(f"\nCredit tier distribution:")
    for tier in ["Prime", "Near-Prime", "Recovering"]:
        count = (users["credit_tier"] == tier).sum()
        pct = count / len(users) * 100
        avg_score = users[users["credit_tier"] == tier]["credit_score"].mean()
        avg_propensity = users[users["credit_tier"] == tier]["baseline_propensity"].mean()
        print(f"  {tier:<15} {count:>6,} ({pct:.1f}%) | avg score: {avg_score:.0f} | avg propensity: {avg_propensity:.4f}")

    print(f"\nCOL distribution:")
    for col in ["HCOL", "MCOL", "LCOL"]:
        count = (users["col_tier"] == col).sum()
        avg_income = users[users["col_tier"] == col]["annual_income"].mean()
        print(f"  {col:<6} {count:>6,} | avg income: ${avg_income:,.0f}")

    overall_propensity = users["baseline_propensity"].mean()
    print(f"\nOverall baseline propensity: {overall_propensity:.4f} ({overall_propensity*100:.2f}%)")


if __name__ == "__main__":
    users = generate_population()
    summarize_population(users)
