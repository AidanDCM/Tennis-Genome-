# Market Layer v1

Status: provider-neutral downstream market/pricing infrastructure. This layer does not change `TGE-Independent-v1` and does not define a betting policy.

## Boundary

The data flow is one-way:

`TGE-Independent-v1 -> canonical market snapshot -> no-vig comparison -> later policy research`

The independent engine never imports this package and never receives bookmaker, odds, no-vig, edge, EV, stake, outcome, CLV, or profit information.

## Raw market snapshot

`MarketSnapshot` represents one observed two-way pre-match `h2h` price from one bookmaker.

Required source/provenance fields include:

- canonical `match_id`;
- provider and bookmaker;
- provider event ID;
- provider/bookmaker observation timestamp;
- local collection timestamp;
- optional event commencement timestamp;
- canonical player A/B IDs;
- provider selection names mapped to A/B;
- decimal prices for both sides;
- raw source payload SHA-256;
- deterministic identity-resolution SHA-256;
- live/suspended state.

The raw snapshot does **not** store no-vig probability, model edge, expected value, stake, or outcome.

## Identity resolution

External market selections must be mapped to canonical Tennis Genome player IDs before a snapshot can enter the comparison layer.

The resolution record is independently hashed. A caller may not infer A/B orientation solely from provider order, home/away labels, or alphabetical order.

Supported resolution methods in v1:

- provider-ID mapping;
- exact verified alias;
- explicit manual verification.

Fuzzy matching may be investigated later, but an ambiguous match must fail closed rather than guess.

## Odds representation

Canonical snapshots store decimal odds only. Provider adapters are responsible for converting or requesting the correct source format before construction.

For decimal odds `d`:

`p_raw = 1 / d`

Two-way proportional no-vig normalization is frozen as the first comparison method:

`q_A = (1/d_A) / ((1/d_A) + (1/d_B))`

`q_B = 1 - q_A`

Book margin:

`margin = (1/d_A) + (1/d_B) - 1`

The no-vig method is versioned as `proportional_two_way_v1`. Later Shin/power-method research must create a new method/version rather than silently changing historical comparisons.

## Model comparison

`MarketComparison` joins one frozen `IndependentPrediction` to one canonical market snapshot by `match_id` and calculates:

- raw implied probabilities;
- book margin;
- no-vig A/B probabilities;
- model A/B probabilities;
- probability edge in percentage points;
- quoted-price EV per unit for each side;
- market quote age at comparison time;
- structural eligibility/reason codes.

For quoted decimal odds `d` and model probability `p`:

`EV per unit = p*d - 1`

A positive computed EV is an estimate under the model, **not** evidence that the wager is profitable.

## Structural eligibility versus policy

Market Layer v1 rejects structurally invalid comparisons such as:

- different match IDs;
- live/in-play markets in the pre-match pipeline;
- comparison timestamps before required inputs exist;
- comparisons created after known commencement time;
- suspended markets.

Staleness is deliberately **not** assigned a hard threshold in this layer. The quote age is recorded and the later policy laboratory decides whether, for example, 30 seconds, 5 minutes, or another threshold is acceptable based on empirical evidence and provider behavior.

Likewise this layer does not impose:

- minimum edge;
- minimum EV;
- model-confidence threshold;
- uncertainty threshold;
- stake size;
- BET/PASS action.

## Initial provider adapter

The first parser targets The Odds API v4 `h2h` response shape while remaining optional and network-free inside the package.

The adapter expects decimal prices and uses the provider/event/bookmaker timestamps supplied by the payload. It only emits a canonical snapshot after an explicit `MarketIdentityResolution` has been supplied.

Provider documentation indicates the live odds endpoint exposes event IDs, commencement times, bookmaker update timestamps, `h2h` markets, named outcomes, and prices. Historical featured-market odds are available as timestamped snapshots on supported paid plans, with availability from June 2020 for covered sports/bookmakers. Provider coverage and licensing remain external dependencies and must be verified for the intended production use.

References:

- https://the-odds-api.com/liveapi/guides/v4/
- https://the-odds-api.com/historical-odds-data/

No API key is stored in the repository. Network acquisition/credentials are deployment concerns, not parser logic.

## Research status

This implementation makes market data reproducible enough to begin a market-data acquisition and policy-research program. It does **not** establish:

- historical sportsbook edge;
- positive EV accuracy;
- CLV;
- ROI;
- profitability;
- a recommended bet;
- a production staking policy.

Those require timestamped market history and later forward paper evidence.
