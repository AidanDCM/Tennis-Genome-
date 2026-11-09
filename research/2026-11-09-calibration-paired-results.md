# Iteration 4 — executed workflow numerical results (paper-only)

Workflow: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42694781390
Code commit b3a71e8c93c63174a8deb280c8f0add86c6e8dc7; job 129423578964, conclusion success; log inspected.
Input: 85 completed eligible WTA Web Shadow paper records; 55 chronological walk-forward evaluations, 30 minimum training observations, all unchanged champion selections (26/55 correct).
Baseline unchanged: Brier 0.263800442657, log loss 0.722770437350.
Adaptive positive-slope challenger: Brier 0.258233234756, log loss 0.710448981532. Mean paired Brier improvement 0.005567207901; naive normal 95% interval [-0.005857111410, 0.016991527212]. Mean paired log-loss improvement 0.012321455818; naive normal 95% interval [-0.013883184799, 0.038526096435]. BOTH intervals cross zero.
Fixed 0.5 slope control (NOT a null control; tests adaptivity versus simple shrinkage): Brier 0.252910042240, log loss 0.698928603610, winner accuracy unchanged 26/55. Relative to raw baseline, paired Brier improvement 0.010890400417, naive 95% interval [-0.005095687034, 0.026876487869]; paired log-loss improvement 0.023841833740, naive 95% interval [-0.012543209172, 0.060226876652]. BOTH intervals cross zero.
Selected adaptive slopes: 0.5 for 25 cases, 0.7 for 30. Fixed 0.5 performed better on this reused sample than adaptive slope selection, a negative finding for the adaptivity hypothesis; no new candidate selected or promoted from this exploratory test.
Caveats: paper-only reused outcomes, model search, temporal clustering, and naive normal intervals make these uncertainty summaries descriptive, not definitive. No prospective forward challenger N.
Next: verify exact-head CI on test commit 0c32a3f31c237e1371cd5005563d5413786ce4dc; use dependence-aware paired intervals and future sealed matches; resolve identity conflicts before expanding sample.
