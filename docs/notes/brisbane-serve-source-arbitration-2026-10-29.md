# Brisbane ATP serve-stat source arbitration, 2026-10-29

**Decision:** The retained Sportradar Brisbane 2026 first/second-serve splits are not qualified for source replacement. Official ATP Stats Centre lines support the pinned history in this small diagnostic sample and reveal split differences even where Sportradar passes internal point conservation. This is a retrospective source audit, not a new forecast or a tournament-wide error-rate estimate.

## Fixed comparison

The three matches were selected from already-retained Brisbane overlap rows: one known partial Sportradar line and two complete lines with equal service-point denominators but differing first-serve counts. Selection was therefore intentionally diagnostic. The ATP pages were read on 2026-10-29, after the player pair and event had been fixed. Joins used both player names, tournament, year, score, and the retained Sportradar event ID. The pinned ATP 2026 CSV SHA-256 is `ceb157ae698f79f4148f7bb6253bbcf6a8c8eb9ff94670dd83aa0428802cfd59`. The retained Sportradar rows came from the earlier season-summary capture for `sr:season:133515`; no new provider request was made.

| ATP match page | Sportradar event | Official first serves in, player order on page | Sportradar first serves in |
| --- | --- | --- | --- |
| [Halys–Nakashima](https://www.atptour.com/en/scores/stats-centre/live/2026/339/ms015) | `sr:sport_event:67291728` | 35/56; 44/60 | 22/36; 13/16 |
| [Vukic–Tiafoe](https://www.atptour.com/en/scores/stats-centre/live/2026/339/MS017) | `sr:sport_event:67364778` | 26/46; 28/39 | 29/46; 29/39 |
| [Ugo Carabelli–Tien](https://www.atptour.com/en/scores/stats-centre/live/2026/339/ms023) | `sr:sport_event:67364770` | 38/66; 36/61 | 40/66; 39/61 |

For all six player rows, the pinned CSV agrees with ATP on aces, double faults, service points, first serves in, first-serve points won, and second-serve points won: **36/36 checked values**. Sportradar matches ATP on aces in **4/6** rows and double faults in **5/6**; all of those mismatches occur in the partial Halys–Nakashima event. Its service-point denominator matches on only four rows: the Halys–Nakashima record has 52 combined service points while ATP reports 116, matching the 116 combined total points in the provider record. The existing match-point conservation guard therefore rejects that partial event.

For the other two matches, the Sportradar service-point denominators and aggregate service wins agree with ATP for all four player rows, but first serves in agree on **0/4**, first-serve points won on **1/4**, and second-serve points won on **1/4**. For example, ATP/pinned give Vukic 15/26 first-serve points won and 7/20 second-serve points won; Sportradar gives 16/29 and 6/17. Both sum to 22 service points won. Point conservation alone cannot detect this split disagreement.

## Source admission

Keep the Brisbane Sportradar serve-split fields out of any source substitution unless an exact event and field is corroborated by authoritative match evidence. The comparison does not diagnose whether the difference arose from collection, a later revision, or a field-definition issue. It does not establish a representative mismatch rate for Brisbane or ATP as a whole. No frozen definition, registered experiment, or prospective prediction changes. The next source-quality step is a predeclared random sample from a broader ATP non-Slam tournament set, with official pages checked before any season-wide admission; expand the WTA official comparison separately.
