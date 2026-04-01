# A/B Testing Fundamentals — Reference Guide

## Why A/B Test?

The core problem: you can't observe the counterfactual. An A/B test creates a synthetic counterfactual through randomization. Treatment and control groups experience the same time period, same market conditions, same seasonality — the only systematic difference is the change you made.

Before/after comparison fails because confounders (seasonality, market shifts, other changes) are inseparable from the treatment effect.

## Hypothesis Testing

- Null hypothesis (H0): the change has no effect. Any observed difference is random noise.
- Alternative hypothesis (H1): the change has an effect.
- p-value: probability of seeing a result this extreme or more, IF H0 is true. Small p = unlikely under null = evidence against null.
- We reject H0 when p < alpha.

## Error Types

| | H0 is true (no effect) | H0 is false (real effect) |
|---|---|---|
| Reject H0 | Type I error (false positive) | Correct |
| Fail to reject H0 | Correct | Type II error (false negative) |

- Alpha = P(Type I) = significance level. Typically 0.05.
- Beta = P(Type II). Power = 1 - Beta. Typically 0.80.
- In financial services: Type I is worse (rolling out something that increases risk). Use alpha = 0.01 for guardrails.

## Alpha Selection

- 0.05: standard for primary metrics
- 0.01: conservative, for high-risk contexts or guardrail metrics
- 0.10: permissive, for exploratory tests or low-stakes contexts
- Trade-off: lower alpha = need more data = longer test

## Power Analysis

Four inputs:
1. Baseline rate (current metric value)
2. MDE (smallest lift worth detecting — BUSINESS decision, not statistical)
3. Alpha (significance threshold)
4. Power (probability of detecting real effect — typically 0.80)

Output: required sample size per group.

Key relationships:
- Smaller MDE → more users needed (quadratic relationship)
- Higher power → more users needed
- Lower alpha → more users needed
- Lower baseline rate → more users needed (fewer events = more noise)

## MDE Decision

MDE is decided by the PM/business, constrained by available traffic.
Question: "What's the smallest improvement that justifies the cost of this change?"
If available sample can't detect the business MDE → renegotiate MDE or don't run the test.

## Randomization

Hash-based: variant = hash(user_id + experiment_id) % 100
- Deterministic: same user always same variant
- No leakage between sessions
- Fresh randomization per test (different experiment_id)
- Balance check post-assignment: verify treatment/control are balanced on covariates

## Sample Ratio Mismatch (SRM)

First thing to check before any analysis.
Expected 50/50 split, got 52/48? Run chi-squared test.
If SRM detected: results are invalid. Fix instrumentation before interpreting.
Common causes: feature fails to load for some users, assignment bug, bot traffic.

## Peeking Problem

Checking results daily and stopping when p < 0.05 inflates false positive rate to 20-30%.
Solution: set duration upfront from power analysis, don't look at primary metric until complete.
Exception: guardrail monitoring is safety, not peeking. Monitor guardrails daily.

## Proportion Test vs Regression

- Two-proportion z-test: headline answer. "Is treatment different from control?"
- Logistic regression with covariates: rigorous answer. Controls for imbalance, estimates adjusted effect, enables HTE through interaction terms.
- Run both. If they agree, confident. If they disagree, investigate the imbalance.

## Multiple Testing

- Sequential tests (our 4 tests): each at alpha = 0.05, each answers different question on different metric. No correction needed across tests, but flag borderline results.
- Multi-arm test (Test 3, 3+ variants): pairwise comparisons need Bonferroni or Holm correction WITHIN that test.
- Bonferroni: divide alpha by number of comparisons. Conservative.
- Holm-Bonferroni: step-down procedure. Less conservative, more power.
- Benjamini-Hochberg: controls FDR not FWER. What most tech companies use.

## Heterogeneous Treatment Effects (HTE)

Not all users respond equally. Interaction terms in regression: treatment x segment.
Pre-register segments before seeing results: credit tier, tenure, income, digital engagement.
Exploratory findings labeled as such — recommend follow-up test to confirm.
Business value: "the feature works especially well for segment X" enables targeted rollout.

## Novelty and Primacy Effects

- Novelty: users engage because it's new, not because it's better. Effect fades over time.
- Primacy: users resist change, engagement dips initially then recovers.
- Solution: run test long enough for effects to stabilize. Monitor metric over time, not just endpoint.

## A/A Testing

Run experiment with no change — both groups get same experience.
Purpose: verify instrumentation, logging, assignment, and analysis pipeline work.
If A/A shows "significant" difference, pipeline is broken.

## Financial Services Specifics

- Guardrail metrics checked with alpha = 0.01 (conservative)
- Fair lending checks are non-negotiable (approval-rate gaps by protected class)
- Risk team sign-off before launch AND before rollout
- Some metrics are lagging (first-payment default takes 30+ days to observe)
- Escalation plan: DS monitors daily, Risk Lead has kill authority

## Interview Answer Template

"I'd start by defining the business question and metric — what are we changing, what lift justifies the change. Then hypothesis, randomization unit, eligibility criteria. Map the funnel, define primary, secondary, and guardrail metrics — sitting with risk for compliance guardrails. Power analysis to determine sample size given MDE, alpha, power. Hash-based randomization, event logging, QA checks, A/A test to verify instrumentation. Risk sign-off before launch. Monitor guardrails daily, don't peek at primary metric. Analyze with proportion test and regression, check HTE across pre-registered segments. Package results with effect size, CIs, guardrail status, and segment breakdowns for the go/no-go decision."
