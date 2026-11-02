# Public WTA match-stat check: seven fixed sample cases

Seven previously pending WTA matches in the frozen 28-match API-Tennis
source-check sample were matched to WTA's public tournament match list and
full-match statistics endpoint. `scripts/capture_wta_official_fixed_sample.py`
verifies the retained API-Tennis capture, fixed sample membership, player
names, tournament, draw level, date, finished singles status, winner, and
official stat-row identity before producing a reference file. The raw WTA
responses, request URLs and observation times, SHA-256 manifest, reference,
and adjudication report are retained under ignored local `outputs/` paths.
The seven-case reference is also checked in at
`research/source_adjudication/wta_official_fixed_sample_next_seven.json`
(SHA-256 `520282c5730b88c617be7ec4467b6fb45f29a6f59b4f2c44c20d2bac9588004b`).
The raw public response bytes remain local; their hashes and observation times
are in the local manifest.

The seven fixed cases were London qualifying Vekic–Monnet, Prague
Bartunkova–Tararudee, Cincinnati Bouzas Maneiro–Bondar, Wuhan qualifying
Sonmez–Kraus, Wuhan Jovic–Chwalinska, Chennai qualifying
Morvayova–Falkowska, and Hong Kong qualifying Sasnovich–Lee. Their official
match pages are listed in the retained reference. All seven agree exactly on
**both players' service points won and played**. This used 13 public WTA HTTP
requests and **zero API-Tennis trial requests**. The captured WTA bytes pass
offline hash verification.

Combined with the eight earlier unique reviews, the fixed sample now has
**15 agreeing reviews and 13 pending**: ATP 2 agreeing/12 pending, WTA 13
agreeing/1 pending. The one pending WTA row is a Billie Jean King Cup fixture,
which requires a different official source. The full denominator remains 28.

This is a selected, limited field comparison. It does not check every model
feature, establish independence between the providers' upstream feeds,
certify WTA `MatchTimeStamp` as actual start, license bulk production use,
approve API-Tennis as a production history source, or create a prospective
prediction. Qualifiers and team events must be separated from the frozen
main-tour population in any later source-quality estimate.

Next: assess official ATP match-stat availability for the 12 pending ATP
cases and the appropriate Billie Jean King Cup source for the last WTA case.
Keep unavailable official counts explicitly pending or unavailable rather
than replacing them with unverified third-party values.
