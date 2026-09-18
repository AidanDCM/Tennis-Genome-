from __future__ import annotations

import json
from pathlib import Path

from scripts import wta_live_prediction_forward_004 as forward


def main() -> None:
    module = forward._load_forward_module()
    h = module.h
    by_name, _ = h.player_index(Path("data/wta_players.csv"))

    trusted_root = Path("trusted-provider-artifact")
    summaries = forward._load_provider_summaries(
        trusted_root / "trusted-provider-capture" / "pages"
    )
    observed_at = forward._capture_observed_at(
        trusted_root / "provider_batch_anchor_receipt.json"
    )
    slate = forward.select_forward_004_targets(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed_at,
    )

    receipt = json.loads(
        (trusted_root / "provider_batch_anchor_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    provider_batch_record_sha256 = str(receipt["batch_record_sha256"])
    anchor_comment_id = int(
        (trusted_root / "provider_batch_anchor_comment_id.txt")
        .read_text(encoding="utf-8")
        .strip()
    )

    targets: list[dict[str, str]] = []
    for _, raw in slate:
        item = dict(raw)
        item["provider_batch_record_sha256"] = provider_batch_record_sha256
        item["provider_anchor_comment_id"] = str(anchor_comment_id)
        targets.append(item)
    resolution_manifest = {
        "schema_version": "wta-forward-004-slate-resolution-v1",
        "forward_protocol": forward.FORWARD_PROTOCOL,
        "selection_rule": (
            "all_confirmed_resolvable_wta_main_tour_singles_sorted_by_start_then_event_id"
        ),
        "minimum_capture_lead_minutes": int(
            forward.MIN_CAPTURE_LEAD.total_seconds() // 60
        ),
        "capture_observed_at": observed_at.isoformat(),
        "eligible_target_count": len(targets),
        "provider_batch_record_sha256": provider_batch_record_sha256,
        "provider_anchor_comment_id": anchor_comment_id,
        "targets": targets,
    }
    Path("forward-004-slate-resolution.json").write_text(
        json.dumps(resolution_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    execution = forward.run_forward_004_slate(
        module=module,
        slate=slate,
        provider_batch_record_sha256=provider_batch_record_sha256,
        provider_anchor_comment_id=anchor_comment_id,
        output_root=Path("slate-prediction-work"),
    )
    print(
        json.dumps(
            {
                "schema_version": "wta-forward-slate-run-summary-v1",
                "eligible_target_count": len(targets),
                "predicted_target_count": execution["target_count"],
                "provider_unique_request_count": execution[
                    "provider_unique_request_count"
                ],
                "lifecycle_chain_head_sha256": execution[
                    "lifecycle_chain_head_sha256"
                ],
                "results": execution["results"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
