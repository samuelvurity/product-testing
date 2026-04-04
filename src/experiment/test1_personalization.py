"""
Test 1: Targeting / Personalization

Control: Generic "You're pre-approved for a personal loan" banner
Treatment: Personalized "You could save $X/month" message based on customer profile

Primary metric: Offer acceptance rate
Secondary: Application start rate
Guardrails: Fair lending gap, complaint rate, fraud proxy rate
"""

import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.power import NormalIndPower
import hashlib
import matplotlib.pyplot as plt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from config.project_config import (
    SAMPLE_SIZE_PER_GROUP, ALPHA, POWER, RANDOM_SEED
)

np.random.seed(RANDOM_SEED)

PLOTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'plots', 'test1')
RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'results', 'test1')

TREATMENT_EFFECT = {
    "Prime": 0.015,
    "Near-Prime": 0.022,
    "Recovering": 0.035,
}

GUARDRAIL_THRESHOLDS = {
    "fair_lending_gap": {"pause": 0.015, "kill": 0.020},
    "complaint_rate": {"pause": 0.002, "kill": 0.005},
    "fraud_proxy_rate": {"pause": 0.005, "kill": 0.010},
}


def run_power_analysis(baseline_rate):
    print("=" * 60)
    print("POWER ANALYSIS")
    print("=" * 60)

    mde_absolute = 0.012
    treatment_rate = baseline_rate + mde_absolute

    effect_size = (
        2 * np.arcsin(np.sqrt(treatment_rate))
        - 2 * np.arcsin(np.sqrt(baseline_rate))
    )

    analysis = NormalIndPower()
    required_n = int(np.ceil(
        analysis.solve_power(
            effect_size=effect_size,
            alpha=ALPHA,
            power=POWER,
            alternative='two-sided'
        )
    ))

    print(f"  Baseline rate: {baseline_rate:.3%}")
    print(f"  MDE: {mde_absolute:.3%} absolute ({mde_absolute/baseline_rate:.0%} relative)")
    print(f"  Alpha: {ALPHA}")
    print(f"  Power: {POWER}")
    print(f"  Cohen's h: {effect_size:.4f}")
    print(f"  Required per group: {required_n:,}")
    print(f"  Using per group: {SAMPLE_SIZE_PER_GROUP:,}")

    if SAMPLE_SIZE_PER_GROUP >= required_n:
        print(f"  Status: ADEQUATE")
    else:
        detectable_effect = analysis.solve_power(
            nobs1=SAMPLE_SIZE_PER_GROUP, alpha=ALPHA, power=POWER, alternative='two-sided'
        )
        detectable_mde = (
            np.sin(detectable_effect / 2 + np.arcsin(np.sqrt(baseline_rate)))
        ) ** 2 - baseline_rate
        print(f"  Status: UNDERPOWERED for {mde_absolute:.3%} MDE")
        print(f"  Detectable MDE at n={SAMPLE_SIZE_PER_GROUP:,}: {detectable_mde:.3%}")

    return required_n


def randomize_users(users, experiment_id="TEST1_PERSONALIZATION"):
    print("\n" + "=" * 60)
    print("RANDOMIZATION")
    print("=" * 60)

    def assign_variant(user_id):
        hash_input = f"{user_id}_{experiment_id}"
        hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        return "treatment" if hash_val % 100 < 50 else "control"

    users = users.copy()
    users["variant"] = users["user_id"].apply(assign_variant)

    treatment_pool = users[users["variant"] == "treatment"]
    control_pool = users[users["variant"] == "control"]

    treatment_sample = treatment_pool.sample(n=SAMPLE_SIZE_PER_GROUP, random_state=RANDOM_SEED)
    control_sample = control_pool.sample(n=SAMPLE_SIZE_PER_GROUP, random_state=RANDOM_SEED)

    experiment_users = pd.concat([treatment_sample, control_sample], ignore_index=True)

    print(f"  Total eligible: {len(users):,}")
    print(f"  Treatment pool: {len(treatment_pool):,}")
    print(f"  Control pool: {len(control_pool):,}")
    print(f"  Sampled treatment: {len(treatment_sample):,}")
    print(f"  Sampled control: {len(control_sample):,}")
    print(f"  Total in experiment: {len(experiment_users):,}")

    return experiment_users


def check_srm(experiment_users):
    print("\n" + "=" * 60)
    print("SAMPLE RATIO MISMATCH CHECK")
    print("=" * 60)

    treatment_n = (experiment_users["variant"] == "treatment").sum()
    control_n = (experiment_users["variant"] == "control").sum()
    total = treatment_n + control_n

    chi2, p_value = stats.chisquare([treatment_n, control_n], [total / 2, total / 2])

    print(f"  Treatment: {treatment_n:,}")
    print(f"  Control: {control_n:,}")
    print(f"  Ratio: {treatment_n/total:.4f} / {control_n/total:.4f}")
    print(f"  Chi-squared: {chi2:.4f}")
    print(f"  p-value: {p_value:.4f}")
    print(f"  SRM detected: {'YES — INVESTIGATE' if p_value < 0.01 else 'NO — balanced'}")

    return p_value


def check_balance(experiment_users):
    print("\n" + "=" * 60)
    print("BALANCE CHECKS")
    print("=" * 60)

    treatment = experiment_users[experiment_users["variant"] == "treatment"]
    control = experiment_users[experiment_users["variant"] == "control"]

    numeric_vars = ["credit_score", "annual_income", "account_tenure_months",
                     "debt_to_income", "days_since_last_login", "existing_products",
                     "baseline_propensity"]

    print(f"\n  {'Variable':<25} {'Control Mean':>14} {'Treatment Mean':>14} {'Diff':>8} {'p-value':>10} {'Balanced':>10}")
    print("  " + "-" * 85)

    for var in numeric_vars:
        ctrl_mean = control[var].mean()
        treat_mean = treatment[var].mean()
        diff = treat_mean - ctrl_mean
        t_stat, p_val = stats.ttest_ind(treatment[var], control[var])
        balanced = "YES" if p_val > 0.05 else "NO ⚠️"
        print(f"  {var:<25} {ctrl_mean:>14.4f} {treat_mean:>14.4f} {diff:>+8.4f} {p_val:>10.4f} {balanced:>10}")

    categorical_vars = ["credit_tier", "col_tier", "age_bracket", "gender", "ethnicity", "region"]

    print(f"\n  Categorical balance (chi-squared):")
    for var in categorical_vars:
        contingency = pd.crosstab(experiment_users["variant"], experiment_users[var])
        chi2, p_val, dof, expected = stats.chi2_contingency(contingency)
        balanced = "YES" if p_val > 0.05 else "NO ⚠️"
        print(f"  {var:<25} chi2={chi2:>8.3f}  p={p_val:>8.4f}  {balanced}")


def simulate_outcomes(experiment_users):
    print("\n" + "=" * 60)
    print("SIMULATING OUTCOMES")
    print("=" * 60)

    results = experiment_users.copy()
    offer_accepted = []
    app_started = []
    fraud_flag = []
    complaint_flag = []

    for _, row in results.iterrows():
        base_prob = row["baseline_propensity"]

        if row["variant"] == "treatment":
            lift = TREATMENT_EFFECT.get(row["credit_tier"], 0.015)

            if row["app_usage_frequency"] in ["daily", "weekly"]:
                lift *= 1.3
            if row["age_bracket"] in ["22-30", "31-40"]:
                lift *= 1.2

            prob = base_prob + lift
        else:
            prob = base_prob

        accepted = 1 if np.random.random() < prob else 0
        started = 1 if accepted and np.random.random() < 0.65 else 0
        fraud = 1 if np.random.random() < 0.003 else 0
        complaint = 1 if np.random.random() < 0.001 else 0

        offer_accepted.append(accepted)
        app_started.append(started)
        fraud_flag.append(fraud)
        complaint_flag.append(complaint)

    results["offer_accepted"] = offer_accepted
    results["app_started"] = app_started
    results["fraud_flag"] = fraud_flag
    results["complaint_flag"] = complaint_flag

    treatment = results[results["variant"] == "treatment"]
    control = results[results["variant"] == "control"]

    print(f"  Control acceptance rate: {control['offer_accepted'].mean():.4f} ({control['offer_accepted'].mean()*100:.2f}%)")
    print(f"  Treatment acceptance rate: {treatment['offer_accepted'].mean():.4f} ({treatment['offer_accepted'].mean()*100:.2f}%)")
    print(f"  Raw lift: {treatment['offer_accepted'].mean() - control['offer_accepted'].mean():.4f} ({(treatment['offer_accepted'].mean() - control['offer_accepted'].mean())*100:.2f}pp)")

    return results


def run_proportion_test(results):
    print("\n" + "=" * 60)
    print("PROPORTION TEST (Headline Analysis)")
    print("=" * 60)

    treatment = results[results["variant"] == "treatment"]
    control = results[results["variant"] == "control"]

    metrics = {
        "Offer Acceptance": "offer_accepted",
        "Application Start": "app_started",
    }

    test_results = {}

    for metric_name, col in metrics.items():
        ctrl_rate = control[col].mean()
        treat_rate = treatment[col].mean()
        ctrl_n = len(control)
        treat_n = len(treatment)
        ctrl_successes = int(control[col].sum())
        treat_successes = int(treatment[col].sum())

        pooled_p = (ctrl_successes + treat_successes) / (ctrl_n + treat_n)
        se = np.sqrt(pooled_p * (1 - pooled_p) * (1 / ctrl_n + 1 / treat_n))
        z_stat = (treat_rate - ctrl_rate) / se if se > 0 else 0
        p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))

        abs_lift = treat_rate - ctrl_rate
        rel_lift = abs_lift / ctrl_rate * 100 if ctrl_rate > 0 else 0

        diff_se = np.sqrt(
            treat_rate * (1 - treat_rate) / treat_n +
            ctrl_rate * (1 - ctrl_rate) / ctrl_n
        )
        ci_lower = abs_lift - 1.96 * diff_se
        ci_upper = abs_lift + 1.96 * diff_se

        sig = "YES ✓" if p_value < ALPHA else "NO"

        print(f"\n  {metric_name}:")
        print(f"    Control: {ctrl_rate:.4f} ({ctrl_rate*100:.2f}%)")
        print(f"    Treatment: {treat_rate:.4f} ({treat_rate*100:.2f}%)")
        print(f"    Absolute lift: {abs_lift:+.4f} ({abs_lift*100:+.2f}pp)")
        print(f"    Relative lift: {rel_lift:+.1f}%")
        print(f"    z-statistic: {z_stat:.4f}")
        print(f"    p-value: {p_value:.6f}")
        print(f"    95% CI: [{ci_lower*100:+.2f}pp, {ci_upper*100:+.2f}pp]")
        print(f"    Significant at alpha={ALPHA}: {sig}")

        test_results[metric_name] = {
            "control_rate": ctrl_rate,
            "treatment_rate": treat_rate,
            "abs_lift": abs_lift,
            "rel_lift": rel_lift,
            "p_value": p_value,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "significant": p_value < ALPHA,
        }

    return test_results


def run_regression_analysis(results):
    print("\n" + "=" * 60)
    print("REGRESSION ANALYSIS (Rigorous)")
    print("=" * 60)

    df = results.copy()
    df["is_treatment"] = (df["variant"] == "treatment").astype(int)

    credit_dummies = pd.get_dummies(df["credit_tier"], prefix="credit", drop_first=True).astype(float)
    col_dummies = pd.get_dummies(df["col_tier"], prefix="col", drop_first=True).astype(float)
    age_dummies = pd.get_dummies(df["age_bracket"], prefix="age", drop_first=True).astype(float)
    usage_dummies = pd.get_dummies(df["app_usage_frequency"], prefix="usage", drop_first=True).astype(float)

    numeric_cols = df[["is_treatment", "credit_score", "annual_income",
                        "account_tenure_months", "debt_to_income",
                        "days_since_last_login", "existing_products"]].astype(float)

    X = pd.concat([numeric_cols, credit_dummies, col_dummies, age_dummies, usage_dummies], axis=1)
    X = sm.add_constant(X)
    y = df["offer_accepted"].astype(float)

    model = sm.Logit(y, X).fit(disp=0)

    treatment_coef = model.params["is_treatment"]
    treatment_pvalue = model.pvalues["is_treatment"]
    treatment_ci = model.conf_int().loc["is_treatment"]

    marginal_effect = np.mean(
        model.predict(X.assign(is_treatment=1.0)) -
        model.predict(X.assign(is_treatment=0.0))
    )

    print(f"  Treatment coefficient (log-odds): {treatment_coef:.4f}")
    print(f"  Treatment p-value: {treatment_pvalue:.6f}")
    print(f"  Treatment 95% CI (log-odds): [{treatment_ci[0]:.4f}, {treatment_ci[1]:.4f}]")
    print(f"  Average marginal effect: {marginal_effect:+.4f} ({marginal_effect*100:+.2f}pp)")
    print(f"  Significant at alpha={ALPHA}: {'YES ✓' if treatment_pvalue < ALPHA else 'NO'}")

    return model, marginal_effect


def run_hte_analysis(results):
    print("\n" + "=" * 60)
    print("HETEROGENEOUS TREATMENT EFFECTS")
    print("=" * 60)

    treatment = results[results["variant"] == "treatment"]
    control = results[results["variant"] == "control"]

    segments = {
        "Credit Tier": "credit_tier",
        "COL Tier": "col_tier",
        "Age Bracket": "age_bracket",
        "App Usage": "app_usage_frequency",
    }

    hte_results = {}

    for segment_name, col in segments.items():
        print(f"\n  --- {segment_name} ---")
        print(f"  {'Segment':<20} {'Ctrl Rate':>10} {'Treat Rate':>10} {'Lift':>8} {'p-value':>10}")
        print("  " + "-" * 62)

        segment_data = {}
        for seg_val in sorted(results[col].unique()):
            ctrl = control[control[col] == seg_val]["offer_accepted"]
            treat = treatment[treatment[col] == seg_val]["offer_accepted"]

            ctrl_rate = ctrl.mean()
            treat_rate = treat.mean()
            lift = treat_rate - ctrl_rate

            if len(ctrl) > 10 and len(treat) > 10:
                ctrl_successes = int(ctrl.sum())
                treat_successes = int(treat.sum())
                pooled = (ctrl_successes + treat_successes) / (len(ctrl) + len(treat))
                se = np.sqrt(pooled * (1 - pooled) * (1 / len(ctrl) + 1 / len(treat)))
                z = lift / se if se > 0 else 0
                p = 2 * (1 - stats.norm.cdf(abs(z)))
            else:
                p = 1.0

            sig_marker = " *" if p < 0.05 else ""
            print(f"  {str(seg_val):<20} {ctrl_rate:>10.4f} {treat_rate:>10.4f} {lift:>+8.4f} {p:>10.4f}{sig_marker}")

            segment_data[seg_val] = {
                "ctrl_rate": ctrl_rate, "treat_rate": treat_rate,
                "lift": lift, "p_value": p,
            }

        hte_results[segment_name] = segment_data

    return hte_results


def check_guardrails(results):
    print("\n" + "=" * 60)
    print("GUARDRAIL CHECKS")
    print("=" * 60)

    treatment = results[results["variant"] == "treatment"]
    control = results[results["variant"] == "control"]

    all_pass = True

    print("\n  1. Fair Lending (acceptance-rate gap by ethnicity):")
    ctrl_rates = control.groupby("ethnicity")["offer_accepted"].mean()
    treat_rates = treatment.groupby("ethnicity")["offer_accepted"].mean()

    max_gap = 0
    for eth in ctrl_rates.index:
        if eth in treat_rates.index:
            gap = abs(treat_rates[eth] - ctrl_rates[eth])
            max_gap = max(max_gap, gap)
            print(f"    {eth:<15} Ctrl: {ctrl_rates[eth]:.4f}  Treat: {treat_rates[eth]:.4f}  Gap: {gap:.4f}")

    threshold = GUARDRAIL_THRESHOLDS["fair_lending_gap"]
    if max_gap >= threshold["kill"]:
        status = "KILL ⛔"
        all_pass = False
    elif max_gap >= threshold["pause"]:
        status = "PAUSE ⚠️"
        all_pass = False
    else:
        status = "PASS ✓"
    print(f"    Max gap: {max_gap:.4f} | Pause: {threshold['pause']} | Kill: {threshold['kill']} | {status}")

    print("\n  2. Complaint Rate:")
    ctrl_complaint = control["complaint_flag"].mean()
    treat_complaint = treatment["complaint_flag"].mean()
    complaint_diff = treat_complaint - ctrl_complaint
    threshold = GUARDRAIL_THRESHOLDS["complaint_rate"]
    if complaint_diff >= threshold["kill"]:
        status = "KILL ⛔"
        all_pass = False
    elif complaint_diff >= threshold["pause"]:
        status = "PAUSE ⚠️"
        all_pass = False
    else:
        status = "PASS ✓"
    print(f"    Control: {ctrl_complaint:.4f} | Treatment: {treat_complaint:.4f} | Diff: {complaint_diff:+.4f} | {status}")

    print("\n  3. Fraud Proxy Rate:")
    ctrl_fraud = control["fraud_flag"].mean()
    treat_fraud = treatment["fraud_flag"].mean()
    fraud_diff = treat_fraud - ctrl_fraud
    threshold = GUARDRAIL_THRESHOLDS["fraud_proxy_rate"]
    if fraud_diff >= threshold["kill"]:
        status = "KILL ⛔"
        all_pass = False
    elif fraud_diff >= threshold["pause"]:
        status = "PAUSE ⚠️"
        all_pass = False
    else:
        status = "PASS ✓"
    print(f"    Control: {ctrl_fraud:.4f} | Treatment: {treat_fraud:.4f} | Diff: {fraud_diff:+.4f} | {status}")

    print(f"\n  Overall guardrail status: {'ALL PASS ✓' if all_pass else 'ACTION REQUIRED ⚠️'}")
    return all_pass


def generate_plots(results, hte_results):
    os.makedirs(PLOTS_DIR, exist_ok=True)

    treatment = results[results["variant"] == "treatment"]
    control = results[results["variant"] == "control"]

    fig, ax = plt.subplots(figsize=(8, 5))
    rates = [control["offer_accepted"].mean() * 100, treatment["offer_accepted"].mean() * 100]
    bars = ax.bar(["Control\n(Generic)", "Treatment\n(Personalized)"], rates, color=["#5B8DB8", "#E8873D"], width=0.5)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f"{rate:.2f}%", ha='center', fontsize=12, fontweight='bold')
    ax.set_ylabel("Offer Acceptance Rate (%)")
    ax.set_title("Test 1: Personalized vs Generic Loan Offer Messaging")
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'acceptance_rate.png'), dpi=150, bbox_inches='tight')
    plt.close()

    if "Credit Tier" in hte_results:
        fig, ax = plt.subplots(figsize=(10, 5))
        tiers = sorted(hte_results["Credit Tier"].keys())
        ctrl_rates = [hte_results["Credit Tier"][t]["ctrl_rate"] * 100 for t in tiers]
        treat_rates = [hte_results["Credit Tier"][t]["treat_rate"] * 100 for t in tiers]
        x = np.arange(len(tiers))
        width = 0.35
        ax.bar(x - width/2, ctrl_rates, width, label='Control', color='#5B8DB8')
        ax.bar(x + width/2, treat_rates, width, label='Treatment', color='#E8873D')
        ax.set_xticks(x)
        ax.set_xticklabels(tiers)
        ax.set_ylabel("Offer Acceptance Rate (%)")
        ax.set_title("Heterogeneous Treatment Effects — by Credit Tier")
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(PLOTS_DIR, 'hte_credit_tier.png'), dpi=150, bbox_inches='tight')
        plt.close()

    print(f"\n  Plots saved to {PLOTS_DIR}/")


def write_results_summary(test_results, marginal_effect, hte_results, guardrails_pass):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    filepath = os.path.join(RESULTS_DIR, "test1_results.md")

    d = test_results.get("Offer Acceptance", {})

    with open(filepath, "w") as f:
        f.write("# Test 1 Results: Targeting / Personalization\n\n")
        f.write("## Summary\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        f.write(f"| Control acceptance rate | {d.get('control_rate', 0):.2%} |\n")
        f.write(f"| Treatment acceptance rate | {d.get('treatment_rate', 0):.2%} |\n")
        f.write(f"| Absolute lift | {d.get('abs_lift', 0):+.2%} |\n")
        f.write(f"| Relative lift | {d.get('rel_lift', 0):+.1f}% |\n")
        f.write(f"| p-value | {d.get('p_value', 1):.6f} |\n")
        f.write(f"| 95% CI | [{d.get('ci_lower', 0)*100:+.2f}pp, {d.get('ci_upper', 0)*100:+.2f}pp] |\n")
        f.write(f"| Significant | {'Yes' if d.get('significant', False) else 'No'} |\n")
        f.write(f"| Regression marginal effect | {marginal_effect:+.4f} |\n")
        f.write(f"| Guardrails | {'ALL PASS' if guardrails_pass else 'ACTION REQUIRED'} |\n\n")

        f.write("## Decision\n\n")
        if d.get('significant', False) and guardrails_pass:
            f.write("**RECOMMENDATION: Roll out personalized messaging.**\n\n")
            f.write("Personalized messaging becomes the new default. This is the baseline for Test 2.\n")
        elif d.get('significant', False) and not guardrails_pass:
            f.write("**RECOMMENDATION: Hold — guardrail violation requires risk review.**\n")
        else:
            f.write("**RECOMMENDATION: Do not roll out — insufficient evidence of lift.**\n")

        f.write("\n## Heterogeneous Treatment Effects — Credit Tier\n\n")
        if "Credit Tier" in hte_results:
            f.write("| Credit Tier | Control | Treatment | Lift | p-value |\n|---|---|---|---|---|\n")
            for tier in sorted(hte_results["Credit Tier"].keys()):
                dd = hte_results["Credit Tier"][tier]
                f.write(f"| {tier} | {dd['ctrl_rate']:.4f} | {dd['treat_rate']:.4f} | {dd['lift']:+.4f} | {dd['p_value']:.4f} |\n")

    print(f"\n  Results summary written to {filepath}")


def main():
    from data.mock.generate_users import generate_population, summarize_population

    print("GENERATING USER POPULATION")
    print("=" * 60)
    users = generate_population()
    summarize_population(users)

    baseline_rate = users["baseline_propensity"].mean()
    run_power_analysis(baseline_rate)

    experiment_users = randomize_users(users)
    check_srm(experiment_users)
    check_balance(experiment_users)

    results = simulate_outcomes(experiment_users)
    test_results = run_proportion_test(results)
    model, marginal_effect = run_regression_analysis(results)
    hte_results = run_hte_analysis(results)
    guardrails_pass = check_guardrails(results)

    generate_plots(results, hte_results)
    write_results_summary(test_results, marginal_effect, hte_results, guardrails_pass)

    print("\n" + "=" * 60)
    print("TEST 1 COMPLETE")
    print("=" * 60)
    acceptance = test_results.get("Offer Acceptance", {})
    print(f"  Result: {acceptance.get('abs_lift', 0)*100:+.2f}pp lift ({acceptance.get('rel_lift', 0):+.1f}% relative)")
    print(f"  Significant: {'YES' if acceptance.get('significant', False) else 'NO'}")
    print(f"  Guardrails: {'ALL PASS' if guardrails_pass else 'ACTION REQUIRED'}")
    if acceptance.get('significant', False) and guardrails_pass:
        print(f"  Decision: ROLL OUT — personalized messaging becomes new baseline for Test 2")


if __name__ == "__main__":
    main()
