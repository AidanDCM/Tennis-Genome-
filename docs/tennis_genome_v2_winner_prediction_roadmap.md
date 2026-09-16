# Tennis Genome V2 — Winner-Prediction Development Roadmap

Status: **MASTER DEVELOPMENT PLAN — WINNER PREDICTION ONLY**

Date: 2026-09-16

## 1. North Star

Build an autonomous, market-blind tennis prediction system that produces better prospective winner probabilities over time while preserving strict point-in-time truth, reproducibility, and resistance to hindsight bias.

The current objective is **winner prediction**, not wagering. No sportsbook odds, exchange prices, implied probabilities, closing lines, or market-derived signals may enter the prediction engine in this phase.

Future betting/value/execution work is intentionally deferred to a separate system that may consume Tennis Genome probabilities only after those probabilities are frozen.

### Success means

- higher prospective winner accuracy without sacrificing probability quality;
- lower Brier score and log loss;
- stable calibration across time and major tennis regimes;
- fewer catastrophic confidence errors;
- reliable uncertainty estimates and sensible abstention/ranking behavior;
- reproducible pre-match snapshots and immutable predictions;
- improvement that survives chronological testing and genuine forward shadow evaluation;
- no silent outcome leakage, same-day leakage, source ambiguity, or post-hoc rule changes.

## 2. Non-negotiable scientific rules

1. **The existing production champion remains immutable.** Existing prospective predictions and settlements are never regenerated or rewritten.
2. **No market data enters the winner model.** Betting/value research is a later independent layer.
3. **Every prediction is point-in-time.** Features must be reproducible from information legally available before the prediction cutoff.
4. **Raw provider evidence is retained and hashed before derivation.**
5. **Exact identity and orientation are mandatory.** Ambiguous events fail closed.
6. **Every challenger is registered before protected evaluation.** Its feature schema, source set, training window, hyperparameter family, calibration, and promotion rule receive deterministic fingerprints.
7. **One loss may generate a hypothesis but may not authorize a model change.**
8. **The same prospective match population must be available to champion and eligible challengers.** No cherry-picking after outputs are seen.
9. **Post-result learning may affect only later matches.** It can never modify a prediction already anchored.
10. **Production promotion is evidence-driven.** A challenger must pass historical chronological tests, robustness controls, and forward shadow confirmation before replacing any champion component.

## 3. Current baseline to preserve

The current production champion is `TGE-Independent-v1`.

For WTA, the strict core currently contains 32 direct predictive features:

- overall Elo: 1;
- recent form: 4;
- workload/rest proxy: 7;
- surface/tournament context: 20.

The WTA production path then adds:

- historical k-neighbor residual alignment with `k=100`;
- point-level tennis simulation from estimated serve-point probabilities;
- a frozen meta mapping combining historical alignment and PointSim;
- Elo-only, strict-Core, and A+B disagreement diagnostics;
- history-depth, missingness, and neighbor-distance diagnostics.

The WTA A+B diagnostic additionally includes serve/return and age-fatigue interaction features.

Known limitations already documented in the repository include conservative date-level chronology, incomplete within-event ordering, and unavailable/unadmitted feature families such as exact environmental conditions, injury/health, travel/circadian state, coaching/current events, and detailed style tracking.

The existing repository also explicitly reserves same-day-aware, rolling-refit, or altered state semantics for challengers rather than silent champion modification.

## 4. Target architecture

Tennis Genome V2 should be a system of cooperating modules rather than one increasingly large monolithic model.

### 4.1 Evidence and Data Spine

Responsibilities:

- raw provider capture;
- immutable source hashes;
- exact event identity and player crosswalks;
- point-in-time availability timestamps;
- canonical match/event records;
- source-specific provenance manifests;
- feature snapshot manifests;
- explicit missingness and exclusion reasons.

No modeling layer may bypass this spine.

### 4.2 Champion Runner

Runs the current frozen production model unchanged on every eligible prospective event.

Outputs:

- champion probability;
- component probabilities;
- diagnostics;
- immutable prediction record;
- trusted external anchor.

### 4.3 Challenger Registry and Shadow Runner

Every challenger receives:

- challenger ID and semantic version;
- parent champion ID;
- deterministic config hash;
- code SHA;
- feature schema hash;
- source-manifest hashes;
- training-data window;
- calibration method;
- eligibility/exclusion contract;
- promotion contract.

All registered challengers run in shadow mode on the same pre-match snapshot whenever their required data are available. Their predictions are frozen before result exposure.

### 4.4 Temporal State Engine

Purpose: represent the player as they actually exist at prediction time, not merely as a long-run historical average.

Candidate signals include:

- exact hours since previous match;
- exact prior-match start/end ordering when available;
- matches in previous 24/48/72 hours;
- minutes played in previous 24/48/72 hours;
- sets, games, tiebreaks, deciding sets, and points played;
- tournament-to-date workload;
- round progression and same-event chronology;
- short-term performance decay windows;
- layoff duration;
- comeback state after long inactivity;
- short-rest interaction with age and workload;
- recent serve/return state with explicit uncertainty and sample depth.

Exact same-day state must use trustworthy event chronology. Schedule slots are insufficient when an actual provider `match_started` timeline event is available.

### 4.5 Serve/Return Matchup Engine

Purpose: model the interaction of Player A's strengths with Player B's weaknesses rather than treating player quality as purely additive.

Candidate signals, only where supported by timestamp-safe source data:

- Player A serve strength versus Player B return strength;
- Player B serve strength versus Player A return strength;
- first-serve-in rate and first-serve point effectiveness;
- second-serve effectiveness and vulnerability;
- ace generation versus opponent return profile;
- double-fault tendency and recent instability;
- break-point creation, conversion, and saving;
- return points won by first/second serve faced;
- hold/break tendencies by surface and recent window;
- opponent-adjusted serve and return residuals;
- surface-specific interaction terms;
- left/right matchup only if it proves useful chronologically;
- head-to-head only as a properly shrunk residual feature, never as an unregularized narrative statistic.

The matchup engine should expose interpretable intermediate probabilities before any meta-model blend.

### 4.6 Environment and Court Context Engine

This remains an audited research lane until trustworthy sources exist.

Potential inputs:

- indoor/outdoor;
- temperature;
- humidity;
- wind;
- altitude;
- court-speed proxy or measured court-speed index;
- ball type;
- surface subtype;
- day/night conditions.

No source is admitted merely because the variable sounds useful. Coverage, point-in-time availability, licensing, and historical consistency must be audited first.

### 4.7 Travel and Circadian Engine

Potential inputs:

- prior tournament location;
- distance traveled;
- timezone shift;
- days since arrival proxy;
- continent change;
- travel interaction with short rest.

This requires a deterministic event-location database and strict chronological joins.

### 4.8 Availability / Health Context Engine

Potential inputs:

- verified injury status;
- recent retirement or withdrawal history;
- medical-timeout evidence where legitimately available;
- comeback-from-injury state;
- official pre-match availability statements.

This is high-risk for timestamp leakage and unreliable reporting. It must remain isolated until a source provenance contract is built. Social rumor and unverified claims are not admissible.

### 4.9 Uncertainty and Out-of-Distribution Engine

This module estimates **how much the system should trust its own winner probability**.

Candidate diagnostics:

- component-model disagreement;
- champion-versus-challenger disagreement;
- k-neighbor mean/nearest/kth distance;
- historical shared-player fraction;
- feature missingness;
- minimum prior match depth;
- minimum point-history depth;
- cold-start or comeback state;
- distance from historical feature support;
- prediction sensitivity to small input perturbations;
- ensemble variance;
- recent calibration drift;
- source freshness and timestamp quality;
- regime novelty.

Outputs should include a reproducible trust/uncertainty record. Initially this is diagnostic only. Any shrinkage-to-0.5, abstention rule, or confidence veto requires its own registered challenger experiment.

### 4.10 Calibration Layer

Existing research identifies WTA Beta calibration as a promising development candidate but not forward-confirmed.

Calibration challengers should include a tightly bounded family such as:

- identity;
- frozen Beta;
- frozen Platt;
- recency-weighted candidates only if preregistered before evaluation.

Calibration may change probability quality without changing winner classification. It must therefore be judged primarily by proper scores and calibration diagnostics, while winner accuracy remains a top-line system outcome.

### 4.11 Ensemble / Meta-Decision Layer

Only after component engines are independently characterized should we test a meta-model that learns when each component deserves more or less weight.

Potential inputs:

- champion Core probability;
- geometry/alignment probability;
- PointSim probability;
- temporal-state probability;
- matchup probability;
- calibration outputs;
- uncertainty diagnostics.

Candidate architectures should begin simple and auditable:

- constrained logistic stacking;
- monotonic blending;
- shrinkage/regularized linear meta-models.

Tree ensembles or more complex learners may be tested later but must beat simpler models chronologically and remain interpretable enough to diagnose failures.

## 5. Development sequence

### Phase 0 — Preserve and fingerprint the champion

Build/verify:

- immutable champion manifest;
- exact production feature list;
- code and model artifact hashes;
- live forward ledger compatibility;
- champion output schema.

Gate:

- deterministic replay produces identical predictions from identical snapshots;
- existing prospective records remain untouched.

### Phase 1 — Build the Challenger Framework first

Implement:

- challenger registry;
- challenger configuration schema;
- deterministic challenger semantic hashes;
- shadow prediction records;
- common pre-match snapshot interface;
- champion/challenger side-by-side runner;
- external anchoring of challenger predictions;
- settlement linkage;
- challenger score ledger;
- league-table/report generator.

Why first: every future idea then has a safe experimental home.

Tests:

- challenger cannot read outcome fields;
- challenger cannot mutate champion artifacts;
- same match/snapshot identity is enforced;
- late challenger prediction is rejected;
- duplicate prediction IDs are rejected;
- hash mismatch fails closed;
- settlement orientation must match prediction orientation.

### Phase 2 — Audit and admit a recent exact-time historical panel

Use retained Sportradar Tennis v3 evidence to determine whether timeline `match_started.time` can support a recent exact-time research panel.

Implement:

- season enumeration;
- pagination completeness proof;
- timeline capture;
- raw retention/hashing;
- exact start extraction;
- conflict detection;
- canonical historical crosswalk;
- coverage reports by tour/season/event level;
- exclusion ledger.

Gate before admission:

- preregister coverage/quality threshold before protected comparison;
- prove identity and chronology reproducibility;
- preserve long-history and exact-time panels as separate evidence products.

### Phase 3 — Temporal State V2 challengers

Build exact-time player-state features on the recent panel.

Candidate family must be bounded before results are inspected. Test, for example:

- baseline conservative state;
- exact-rest-only challenger;
- exact workload challenger;
- exact recent serve/return state challenger;
- combined temporal state challenger;
- less-aggressive state update variants already motivated by existing diagnostics.

Evaluation:

- chronological walk-forward only;
- no random split;
- tournament/event grouping controls where appropriate;
- proper-score and accuracy results by year;
- stability across normal, sparse-history, short-rest, and long-layoff regimes.

Promotion path: historical development winner -> independent later shadow sample -> eligible component candidate.

### Phase 4 — Return-specific Matchup V2

First perform a source/data-availability audit for point/stat dimensions.

Then create player-side rolling latent states and cross-player interactions.

Critical comparison:

- additive player-strength baseline;
- serve/return state only;
- cross-matchup interactions only;
- combined matchup engine.

Avoid uncontrolled feature explosion. Use predeclared families and ablations.

### Phase 5 — Failure Atlas and Diagnostic Learning System

Every settled prospective match should create a structured failure/success record containing only immutable pre-match predictions plus post-match outcome diagnostics clearly marked as post-result.

Record:

- champion/challenger probabilities;
- component probabilities;
- disagreement;
- uncertainty diagnostics;
- feature missingness/history depth;
- temporal regime;
- surface/event regime;
- outcome and score;
- post-match serve/return statistics when available;
- loss classification tags generated from fixed deterministic rules.

Purpose: identify repeated error regimes and generate future hypotheses.

Rule: the Failure Atlas may propose research questions but may not directly retune production.

### Phase 6 — Uncertainty Engine

Develop an uncertainty target using historical out-of-sample errors.

Test whether uncertainty diagnostics predict:

- absolute probability error;
- Brier contribution;
- log-loss tail risk;
- upset risk conditional on predicted confidence.

Candidate uses:

- confidence shrinkage;
- abstention/ranking;
- exception flag;
- meta-model input.

Do not introduce a hard veto until it wins its own chronological and forward test.

### Phase 7 — Calibration Challengers

Shadow-run:

- identity champion calibration;
- frozen WTA Beta candidate;
- frozen WTA Platt secondary;
- any newly registered recency-calibration candidate.

Measure:

- accuracy;
- Brier;
- log loss;
- ECE;
- calibration slope/intercept;
- performance by confidence bucket;
- temporal drift.

### Phase 8 — Multi-engine Ensemble

Once Temporal, Matchup, and Uncertainty components have earned evidence independently, register a bounded ensemble family.

Start with simple constrained stacking.

Requirements:

- nested chronological training for meta-model fitting;
- component predictions used for a training row must themselves be out-of-fold/point-in-time;
- no meta-model may train on in-sample base-model probabilities;
- explicit regularization;
- coefficient stability reports;
- ablation tests.

### Phase 9 — Prospective Champion–Challenger League

For every eligible live match:

- Champion produces the official experimental prediction;
- every registered production-ready challenger produces a shadow prediction from the identical evidence cutoff;
- all predictions are externally anchored before start;
- settlement scores them identically.

Maintain cumulative and rolling metrics without changing historical records.

No challenger becomes champion because of one dramatic win/loss.

### Phase 10 — Promotion Protocol

Before each challenger begins protected/forward evaluation, freeze its promotion gate.

A reasonable gate family should require all of the following, with exact numeric tolerances preregistered before results:

- no temporal leakage/provenance failure;
- no material Brier degradation;
- no material log-loss degradation;
- winner accuracy non-inferior and preferably improved;
- improvement not concentrated in one year/tournament/player subset;
- calibration not materially degraded;
- tail-confidence errors not materially worse;
- sufficient forward sample size;
- consistent result under defined robustness analyses;
- reproducible artifacts and exact rerun equality.

Statistical uncertainty and multiple challenger comparisons must be accounted for. Promotion criteria cannot be invented after inspecting challenger outcomes.

### Phase 11 — Champion Cutover

A promoted challenger becomes a new versioned champion, never an in-place mutation.

For example:

- `TGE-Independent-v1` remains permanently reproducible;
- new production might become `TGE-Independent-v2`;
- cutover timestamp and first eligible event are frozen;
- old and new champion artifacts are both retained;
- forward cohort membership is explicit by model version.

### Phase 12 — Continuous Research Cycle

After V2 production cutover, repeat the champion/challenger process indefinitely.

The system is considered operationally complete when autonomous data intake, prediction, anchoring, settlement, scoring, diagnosis, challenger shadowing, and promotion evidence generation work reliably without manual intervention. The research process itself remains intentionally open-ended.

## 6. Daily automation design

### Morning run

For each eligible event:

1. enumerate trusted provider schedule;
2. bind exact event/player identities;
3. confirm singles/tour eligibility;
4. confirm pre-start status;
5. capture and hash raw evidence;
6. build one point-in-time feature snapshot;
7. run champion;
8. run every eligible registered challenger on that same snapshot;
9. record component and uncertainty diagnostics;
10. immutably commit and externally anchor all prospective records;
11. publish a concise morning dossier.

A challenger missing required trustworthy data is explicitly marked unavailable; the system does not fabricate or silently impute prohibited data.

### Night run

For every relevant prediction:

1. query trusted terminal state;
2. capture and hash settlement evidence;
3. bind identities/orientation to the original snapshot;
4. externally anchor settlement;
5. verify unedited commitment and retained provenance;
6. score champion and challengers;
7. update cumulative and rolling metrics;
8. update Failure Atlas;
9. update legal player state for future dates;
10. create hypothesis flags for research review;
11. never mutate the settled prediction.

## 7. Evaluation metrics

### Top-line winner metrics

- winner accuracy;
- accuracy by confidence bucket;
- accuracy by tour/surface/event level;
- favorite/upset directional performance when defined strictly from the model rather than betting markets.

### Proper probability metrics

- Brier score;
- binary log loss;
- ECE;
- calibration slope/intercept;
- reliability curves.

### Robustness metrics

- year-by-year deltas;
- rolling-window deltas;
- source-missingness strata;
- history-depth strata;
- layoff/rest strata;
- model-disagreement strata;
- OOD/neighbor-distance strata;
- confidence-tail loss;
- worst-regime degradation.

### Data/system quality metrics

- provider coverage;
- identity-match rate;
- exact-time coverage;
- feature missingness;
- exclusion counts by reason;
- anchor success rate;
- settlement latency;
- deterministic rerun match rate.

## 8. Testing strategy

### Unit tests

Every feature calculation, orientation transform, timestamp transform, calibration map, and scoring function receives deterministic unit coverage.

### Property/invariant tests

Examples:

- player swap flips orientation but preserves semantic probability;
- probabilities remain finite and sum to one;
- future rows never enter feature state;
- a result timestamp cannot precede prediction cutoff;
- settlement cannot change prediction SHA;
- repeated derivation from identical evidence produces identical feature hashes.

### Temporal leakage tests

Construct adversarial datasets where future information would visibly improve predictions and prove that the production pipeline cannot access it.

Test:

- same-day ordering;
- timezone boundaries;
- rescheduled matches;
- postponed matches;
- tournaments crossing UTC dates;
- duplicate events;
- timeline updates;
- late provider corrections.

### Identity tests

- names with accents/transliteration;
- player renames;
- duplicate/common names;
- replacements/withdrawals;
- qualifier/lucky-loser substitutions;
- reversed competitor ordering.

### Integration tests

Run source capture -> canonicalization -> features -> champion/challenger -> anchor -> settlement -> score entirely from fixtures.

### Reproducibility tests

A retained raw evidence bundle must reconstruct:

- feature snapshot hash;
- model artifact identity;
- prediction probability;
- prediction record SHA;
- settlement score.

### Adversarial/fail-closed tests

Corrupt or remove evidence, timestamps, hashes, IDs, statuses, or anchor bodies and verify the system refuses qualification.

### Statistical tests

- chronological walk-forward;
- nested model selection;
- locked hyperparameter families;
- stability by year/regime;
- bootstrap or other preregistered uncertainty intervals where appropriate;
- multiplicity handling when comparing many challengers.

## 9. Learning from individual losses without overfitting

Each loss triggers three outputs:

1. **Immutable observation:** what the champion/challengers predicted and what happened.
2. **Diagnostic decomposition:** which pre-match components agreed/disagreed and which known uncertainty regimes applied.
3. **Hypothesis queue:** possible explanations to test over future/historical populations.

A single loss never changes a coefficient, threshold, feature set, or production rule.

The hypothesis queue becomes useful only when repeated patterns accumulate.

Examples of legitimate future hypotheses:

- Core confidence is overstated when PointSim is near 50%;
- exact short-rest state improves WTA prediction;
- long layoffs require stronger uncertainty shrinkage;
- recent second-serve instability has incremental predictive value;
- high model disagreement predicts error conditional on confidence.

Each becomes a registered experiment rather than an immediate patch.

## 10. Initial challenger family

Once the challenger framework exists, the first bounded candidates should be:

- `C0`: current `TGE-Independent-v1` champion;
- `C1`: champion + frozen WTA Beta calibration;
- `C2`: exact-time temporal-state challenger;
- `C3`: exact-time recent serve/return-state challenger;
- `C4`: serve-vs-return matchup interaction challenger;
- `C5`: temporal + matchup combined challenger;
- `C6`: uncertainty-shrunk challenger, only after uncertainty research is frozen;
- `C7`: constrained meta-ensemble of independently validated components.

Do not launch all uncontrolled variants simultaneously. Each research phase must define a bounded family and promotion hierarchy before outcome inspection.

## 11. Autonomous development policy

Routine development should proceed without user interruption through:

- branch creation;
- implementation;
- tests;
- lint/type/schema fixes;
- documentation;
- CI;
- evidence verification;
- PR creation/merge when checks are clean and changes preserve protocol boundaries;
- workflow execution;
- diagnostic follow-up.

Stop only when continuation genuinely requires one of:

- a new secret/credential or explicit external authorization;
- provider access/quota the current account does not have;
- a paid purchase or irreversible external action;
- legal/licensing ambiguity that could make evidence use improper;
- a scientific decision with multiple materially different valid North Stars that cannot be resolved from the frozen protocol;
- a destructive repository operation that is not clearly necessary.

Otherwise choose the conservative, reproducible path and continue.

## 12. Deferred betting/value layer

Not part of this roadmap's implementation target.

When winner prediction is sufficiently mature, build a separate system that receives only already-frozen Tennis Genome probabilities and then performs market/value/execution analysis. That future layer may incorporate ideas from quantitative finance such as expected value, uncertainty-aware sizing, portfolio correlation, drawdown control, execution quality, and risk budgeting.

The separation is architectural:

`Tennis truth model -> frozen probability -> future value engine -> future risk/execution engine`

Market information must never leak backward into the market-blind winner-prediction experiment.

## 13. End-state definition

Tennis Genome V2 winner prediction is ready for production consideration when:

- raw and derived evidence are fully point-in-time and reproducible;
- exact-time temporal state is admitted or explicitly unavailable under a documented source boundary;
- matchup engine and uncertainty engine are implemented and tested;
- challenger framework runs autonomously;
- champion and challengers are prospectively shadow-scored;
- failure atlas runs automatically;
- promotion rules are preregistered;
- at least one challenger has legitimately earned promotion through the complete gate;
- daily prediction/settlement workflows operate reliably without weakening trust controls;
- model-version cutover can occur without rewriting any earlier prediction or cohort.

The final principle is simple: **move quickly in research, move slowly in promotion, and never let hindsight rewrite the evidence.**
