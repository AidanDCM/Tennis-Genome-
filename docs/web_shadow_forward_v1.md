# Web Shadow Forward Mode v1

Web Shadow is a **non-production** prospective testing lane for Tennis Genome. It lets the
project freeze predictions against publicly visible future WTA fixtures and settle them later
against public results while limited provider requests are preserved.

## Trust boundary

Web evidence is never Sportradar evidence. Every record has `production_eligible: false`.
Web-shadow records cannot satisfy the trusted-provider capture, full-slate cutover validator,
prospective production evidence store, or `FULL_SLATE_V1` activation gate.

The lane exists to test predictive behavior on genuinely unseen matches, not to certify provider
ingestion or production orchestration.

## Lifecycle

1. Observe an official public fixture before its scheduled start.
2. Normalize the fixture into `WebShadowFixture`, retaining the source URL and observation time.
3. Build the normal Tennis Genome model inputs from information available at that time.
4. Freeze the model input manifest SHA, model source SHA, probabilities, selected player and
   commitment timestamp in a hashed `WEB_SHADOW_PREDICTION` record.
5. After play, observe an official result and append a hashed `WEB_SHADOW_SETTLEMENT`.
6. Aggregate settled records for accuracy, Brier score, log loss and calibration analysis.

Chronology fails closed: both the source observation and prediction commitment must precede the
scheduled start. Settlement observation must follow it. Mutation of a frozen prediction breaks its
SHA-256 verification.

## Initial public sources

Prefer WTA's official score/match pages for fixture identity and settlement. Secondary sources may
be retained as corroboration but should not silently overwrite the official fixture identity.

The first live candidates identified during implementation were the September 19, 2026 Guadalajara
final and Korea Open qualifying matches. Candidate discovery is intentionally outside the production
provider path.
