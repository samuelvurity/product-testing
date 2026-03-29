# Experiment Design Document — Loan Product Adoption

## Background

50K eligible users (out of 300K active) on a financial services lending platform.
Current loan adoption rate: 3.2%. Industry benchmark: 5-7%.
No prior experimentation capability.

## Objective

Optimize the full loan adoption funnel through 4 sequential A/B tests, measuring cumulative lift in adoption rate.

## Scoping Decisions (from stakeholder conversations)

### Product Team
- Primary objective: increase loan adoption rate from 3.2% toward industry benchmark (5-7%)
- "Adoption" defined as: loan application submitted and approved (not just offer click)
- Full funnel optimization: targeting → offer → channel → UX
- No existing funnel data on where drop-offs occur — tests will reveal this

### Risk / Compliance
- Fair lending: 2 percentage point maximum approval-rate gap across monitored segments (race, ethnicity, age, gender). Hard threshold — test pauses immediately if breached.
- UX test: daily monitoring on verification completion and manual review rates
- Every guardrail has a specific pause threshold and kill threshold
- Written sign-off required before each test launches
- Escalation: DS monitors daily, flags Risk Lead if approaching threshold, Risk Lead has kill authority

### Analytics Lead (Methodology)
- Proportion test as headline, regression-based inference for rigor
- Sequential tests: each at alpha = 0.05, with exploratory findings flagged
- Multi-arm test (Test 3) uses Bonferroni/Holm correction for pairwise comparisons
- HTE segments pre-registered: credit tier, account tenure, income bracket, digital engagement
- Fresh randomization per test — winner becomes new default for all users

## Test Sequence

| Test | What's Changing | Primary Metric | Guardrails |
|---|---|---|---|
| 1. Targeting / Personalization | Generic offer vs personalized refinance/savings message | Offer acceptance rate | Approval-rate gap, complaint rate, fraud proxy |
| 2. Offer Design | "Pre-approved" vs "See if you qualify" framing | Application start rate | First-payment default, verification abandonment, cost per booked loan |
| 3. Channel & Timing | Email vs mobile vs website; always-on vs scheduled | Offer response rate | Complaint rate, fraud proxy, approval-rate gap |
| 4. Application UX | Shorter flow vs current flow | Application completion rate | Verification abandonment, manual review rate, first-payment default |

## Statistical Approach

### Per Test
1. Define primary metric, secondary metrics, guardrail metrics with thresholds
2. Power analysis: sample size given baseline rate, MDE, alpha=0.05, power=0.80
3. Randomize from 50K eligible: 4K treatment, 4K control (hash-based, deterministic)
4. Balance checks on pre-experiment covariates
5. Run test for calculated duration (no peeking)
6. Analyze: proportion test (headline) + regression with covariates (rigorous)
7. HTE: pre-registered segment cuts (credit tier, tenure, income, digital engagement)
8. Guardrail check: all metrics within thresholds
9. Results package to product + risk

### Multiple Testing
- 4 sequential tests: each stands at alpha=0.05 independently
- Borderline results (p=0.04-0.05) flagged as marginal
- Test 3 (multi-arm): Bonferroni/Holm correction on pairwise comparisons
- Exploratory HTE findings labeled as such, not used for go/no-go

### Guardrail Thresholds

| Guardrail | Pause Threshold | Kill Threshold | Monitoring |
|---|---|---|---|
| Approval-rate gap (fair lending) | 1.5pp gap | 2.0pp gap | Daily |
| Fraud proxy rate | +50bps vs control | +100bps vs control | Daily week 1, weekly after |
| First-payment default | +30bps vs control | +60bps vs control | Weekly (lagging metric) |
| Verification abandonment | +5pp vs control | +10pp vs control | Daily |
| Manual review rate | +3pp vs control | +5pp vs control | Daily |
| Complaint / escalation rate | +20bps vs control | +50bps vs control | Daily week 1, weekly after |
| Cost per booked loan | +10% vs control | +20% vs control | Weekly |

## Deliverables Per Test

1. Power analysis notebook
2. Randomization + balance check code
3. Analysis code (proportion test, regression, HTE)
4. Guardrail monitoring report
5. Results summary document

## Final Deliverable

Cumulative results package for product leadership + risk sign-off:
- Executive summary with cumulative lift
- Per-test results with winning variants
- Segment-level insights (HTE)
- Revenue projection
- Risk sign-off summary
- Methodology appendix
