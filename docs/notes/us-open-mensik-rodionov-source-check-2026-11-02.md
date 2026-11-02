# US Open fixed-sample source check

The preselected API-Tennis source-check case 12159171 is the 2026-09-03
Mensik–Rodionov US Open men's singles match. The [official US Open IBM
SlamTracker match page](https://www.usopen.org/en_US/scores/stats/1211.html)
reports Mensik's first-serve points won as 44/52 and second-serve points won
as 26/39, yielding **70/91** service points. It reports Rodionov's first-serve
points won as 50/67 and second-serve points won as 20/45, yielding **70/112**.
The retained, receipt-verified API-Tennis record has the same 70/91 and 70/112
counts under exact player IDs 902 and 416. Its date, player orientation,
winner, and finished singles identity agree with the official page.

The official counts were visible in the public search index on 2026-11-02;
a direct request from this environment returned only the US Open's short
client-side shell, so exact official response bytes were **not** captured
locally. The manually transcribed reference is
`research/source_adjudication/us_open_mensik_rodionov_2026.json` and can be
re-adjudicated against the verified retained API-Tennis capture. This is a
research-only check, weaker in provenance than the seven WTA cases whose exact
official JSON bytes were retained. It is not production source admission or
a prospective forecast.

This raises the 28-case fixed sample to **16 exact service-point agreements**
and **12 still pending**: ATP 3 agreeing/11 pending, WTA 13 agreeing/1 pending.
