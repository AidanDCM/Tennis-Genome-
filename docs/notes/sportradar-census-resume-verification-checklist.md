# Resume verification checklist

Before any new historical Sportradar call is permitted, verify all of the following from retained evidence:

- frozen inventory semantic identity matches the source inventory artifact;
- historical candidate denominator matches the frozen inventory;
- retained season directories form one contiguous prefix of that candidate ordering;
- each reusable Season Summaries page/header pair reproduces pagination and season identity;
- the terminal quota response is HTTP 429 and occurs exactly at the frontier;
- no season after the frontier has reusable evidence;
- the reconstructed checkpoint identifies the exact next candidate and preserves cumulative provider-response accounting;
- no active resume request file exists while quota is exhausted.

The current expected checkpoint from the Sep 17 partial census is 79 completed candidates with candidate index 79 / season `sr:season:133607` next. This expectation must be rederived from the actual artifacts before merge; it is not sufficient on its own.
