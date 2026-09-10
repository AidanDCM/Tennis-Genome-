# Genome neighborhood adversarial review

This note records a post-result interpretation constraint discovered during PR review. It does **not** alter GENOME-NN-001, its registered gates, or its accepted historical result.

## What H-011 establishes

Under the frozen GENOME-NN-001 protocol, the k=100 historical residual signal adds small but stable chronological proper-score value beyond the fair Platt-like meta-control on both ATP and WTA, survives the recent-period gates, and survives exclusion of every neighbor sharing either target player.

That is sufficient for the preregistered conclusion: **provisional historical support for an incremental local residual signal**.

## What H-011 does not yet isolate

The primary Genome vector contains the strict Core matchup features themselves. Therefore nearest-neighbor residual averaging can act partly as a **local nonlinear calibration / residual correction of Core probability**.

The fair meta-control in GENOME-NN-001 is intentionally simple:

`logistic(alpha + beta * logit(p_core))`

A positive Genome result against that control does not prove that the gain comes from rich matchup geometry rather than a more flexible nonparametric correction conditioned heavily on Core strength/confidence.

This is not leakage and does not invalidate the registered H-011 pass. It limits interpretation.

## Required next adversary before embeddings

Before promoting historical alignment beyond B / conditional development status, a new preregistered experiment should compare the full Genome neighborhood against stronger controls, including at minimum:

1. a flexible chronological calibration control for `p_core` alone;
2. a Core-only neighborhood using the same k/distance machinery but excluding absolute Profile means;
3. a one-dimensional or low-dimensional strength/confidence-matched residual neighborhood;
4. the full Genome neighborhood on the exact same target population.

The question becomes:

> Does full structured matchup similarity add residual information beyond what can already be recovered from nonlinear calibration and local strength/confidence matching?

Only if the full Genome survives that adversary should the project spend complexity on learned metrics, embeddings, or module-weight optimization.

## Density implication

The same review reinforces the H-012 rejection. Raw neighborhood distance is entangled with Core confidence / match extremity and therefore cannot currently be interpreted as OOD or used for abstention.
