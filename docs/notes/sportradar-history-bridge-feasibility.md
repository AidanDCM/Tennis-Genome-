# Sportradar history bridge feasibility

The retained bounded capture from GitHub run `37037462187` contains six newly
captured season feeds. An offline schema inspection found 262 match summaries:
252 terminal, 251 with two competitor statistics rows. No summary carried a
surface; none of the 524 competitor records carried rank, ranking points, birth
date, handedness, or height. Those fields require independently retained,
time-legal sources. A surface or player identity must not be guessed from a
name or a tournament title.

`sportradar_history_bridge.summary_to_historical_match` is a research-only
conversion gate. It requires an explicit reviewed provider-to-canonical player
crosswalk and season-surface mapping, a source-observation time no later than
the target cutoff, a confirmed scheduled event time from a prior UTC day, a
terminal non-walkover result, and internally consistent point statistics. It
uses each event's date rather than `season.start_date`, orients player A/B by
canonical ID, and maps WTA levels using the existing frozen live semantics.
Missing ranks and demographics remain missing.

An exploratory mechanical pass over the 262 summaries, using provider IDs as
temporary identities and an explicit `Unknown` surface, converted 164 ATP and
85 WTA matches before the additional confirmed-time guard was added. Ten were
nonterminal, one had an excluded finish, and two had contradictory serve totals.
These placeholder conversions are **not** usable frozen-model history or
prospective evidence. The real gate still requires reviewed identity mappings,
surface and profile sources, duplicate reconciliation with the pinned 2026
archive, and a retained source receipt before current-state assembly.

The existing ATP PATTERN-CONFIRM adapter sets historical `event_date` from the
season start. Do not reuse that behavior in the general frozen-model history
builder. A confirmed scheduled time is also not proof of actual start for the
prospective evidence protocol.
