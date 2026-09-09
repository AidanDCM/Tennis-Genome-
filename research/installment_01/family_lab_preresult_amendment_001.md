# Foundational Family Lab — Pre-Result Amendment 001

This amendment was committed **before reading or classifying any completed foundational-family result**.

## Reason

A source-semantic audit identified that the Sackmann ATP `tourney_level` code `D` represents Davis Cup, not lower-tier competition. The original exploratory feature builder had grouped `C` and `D` together under an internal `lower_tier_elo` label.

That label is not valid enough for an accepted experiment.

## Accepted-run change

`lower_tier_elo` is excluded from `surface_tournament_context` in the accepted family laboratory.

The accepted context family therefore tests only the context variables whose semantics are sufficiently clear in the current representation, including surface interactions, Grand Slam / Masters / finals codes where present, late-round / round-robin / best-of-five interactions, and player seed/entry-status features.

Davis Cup / team-event context is **not** silently reclassified as lower tier.

A dedicated team-event feature can be registered later if source coverage and tour-specific level semantics are audited explicitly for both ATP and WTA.

## Scientific consequence

Any family-lab artifact produced from a commit before this amendment is ineligible for acceptance, even if its metrics are favorable. Only a later exact-head run that includes this amendment may be classified.
