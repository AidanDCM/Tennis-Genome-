# Bounded 2026 historical continuation

The 2026 Jeff Sackmann archive currently used by the offline engineering replay
ends at tournament date 2026-05-25. A retained Sportradar inventory captured on
2026-09-16 contains 45 ATP/WTA singles season feeds starting 2026-05-26 through
2026-10-02. Four are already complete in the retained partial census. This
inventory may miss seasons added after its capture; refresh it before claiming
complete 2026 coverage.

`scripts/capture_sportradar_targeted_2026.py` reads the verified inventory and
optionally reuses a retained census directory. `--max-requests 0` performs an
offline audit and makes no provider calls. For a live run, explicitly set a
positive cap (at most 50) and provide `SPORTRADAR_API_KEY` in the environment.
The transport performs one HTTP attempt per request, including on HTTP 429. A
run can stop mid-season; rerunning with the same output directory resumes from
the next retained page. Response bodies and headers are retained. The run
report records the cap and actual attempts.

This is historical research collection. It does not reconstruct legal pre-match
states, establish forward eligibility, or produce frozen production predictions.
The local output directory must be preserved between runs. Provider responses
and the inventory remain subject to source licensing and provenance review.
