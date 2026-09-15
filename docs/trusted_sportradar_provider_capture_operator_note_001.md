# Operator note

The trusted provider capture workflow is intended to be manually dispatched only after its implementation and frozen source identities are merged to `main` and exact-head CI is green.

The only operator choices are the UTC schedule date and `trial`/`production` Sportradar access level. Do not supply provider payloads, hashes, observation timestamps, or anchor timestamps by hand.
