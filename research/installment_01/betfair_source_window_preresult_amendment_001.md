# Betfair Historical Source Window — Pre-Result Amendment 001

Status: **FROZEN BEFORE LICENSED BETFAIR OUTCOME INSPECTION**

## Reason for amendment

Current official Betfair Developer Program documentation states that Stream-format Betfair Historical Data is available from **April 2015** and that data before that date is not available in this format. Australian/New Zealand-based market data is available from October 2016 only.

Earlier Tennis Genome research uses canonical tennis history reaching back to 2000, but the market-aware experiments cannot truthfully claim a Betfair market sample for those pre-2015 years.

This amendment is made before licensed Betfair market outcomes are inspected and therefore does not respond to model performance.

## Frozen source boundary

For `BETFAIR_HISTORICAL` Stream-format source manifests used by MARKET-HIST-QA / MARKET-EDGE research:

- `requested_start_date` must be on or after `2015-04-01`;
- `requested_end_date` remains on or before `2025-12-31` for the frozen development program;
- the actual purchased/downloaded contiguous source interval must be declared exactly;
- MARKET-HIST-QA continues to compute its denominator only inside that declared interval;
- no synthetic or absent pre-April-2015 Betfair observations may be created to extend market history.

If the acquired bundle begins later than April 2015, its true later start date is used. The existence of an April-2015 service boundary does not authorize pretending every April-2015 tennis market is present.

## Interpretation correction

Any MARKET-EDGE or MARKET-EDGE-ADV result must be described as applying to the **available licensed Betfair historical interval through 2025**, not to a 2000-2025 Betfair sample.

Pre-2015 canonical tennis history may still contribute to the already-frozen tennis models that generated honest out-of-sample features/probabilities, but it is not market-comparison data.

## Chronology and power

No statistical gate changes:

- chronological evaluation remains year-forward;
- at least 1,000 earlier matched market rows are still required before an evaluation year;
- MARKET-HIST-QA coverage gates remain unchanged;
- POWER-MDE-001 remains outcome-blind;
- MARKET-EDGE-001 and MARKET-EDGE-ADV-001 promotion/multiplicity gates remain unchanged;
- 2026+ remains forbidden for development.

The first confirmatory evaluation year is therefore determined mechanically by how quickly the licensed post-2015 market sample accumulates 1,000 eligible earlier rows. It is not fixed in advance or chosen after results.

## Australian/New Zealand caveat

Official Betfair documentation states that Australian/New Zealand-based historical market data begins in October 2016. MARKET-HIST-QA coverage and subgroup diagnostics must expose any resulting early-era geographic/event selection effects rather than silently treating missing markets as model failures or imputing them.

No special post-result reweighting or exclusion is authorized by this amendment.

## Non-claims

This amendment does not add evidence for Profile Gap, Genome, market incrementality, EV, CLV, ROI, or profitability. It only aligns the source contract with the documented historical availability of the intended provider.
