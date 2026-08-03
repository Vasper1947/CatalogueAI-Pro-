"""Classifier tests (synthetic schemas, no disk)."""

from schemas.classify import CLASSIFY_THRESHOLD, classify_category, top_suggestion


def _schema(path, *, naming="", breadcrumb=""):
    return {
        "category_path": path,
        "instructions": {"naming_convention": naming, "breadcrumb": breadcrumb},
    }


def test_close_match_ranks_highest_with_matched_words():
    schemas = [
        _schema(
            ["Finishing & Decoration", "Mouldings & Cornices", "Floor Skirting Boards", "PVC Skirting"],
            naming="Pattern: [Brand] PVC Skirting Board",
            breadcrumb="Finishing & Decoration > Mouldings & Cornices > Floor Skirting Boards > PVC Skirting",
        ),
        _schema(
            ["Plumbing & Sanitary Ware", "Sanitary Ware", "Wash Basins & Pedestals", "Vessel Basins"],
            naming="Pattern: [Brand] Vessel Basin",
            breadcrumb="Plumbing & Sanitary Ware > Sanitary Ware > Wash Basins & Pedestals > Vessel Basins",
        ),
    ]
    ranked = classify_category("White PVC skirting board for floor edges", schemas)

    assert ranked[0].category_path[-1] == "PVC Skirting"
    assert "skirting" in ranked[0].matched_terms
    assert ranked[0].score > ranked[1].score


def test_unrelated_text_scores_below_threshold_no_forced_pick():
    schemas = [
        _schema(
            ["Tools & Equipment", "Power Tools", "Drills", "Cordless"],
            naming="Pattern: [Brand] Cordless Drill",
            breadcrumb="Tools & Equipment > Power Tools > Drills > Cordless",
        )
    ]
    ranked = classify_category("banana yoghurt smoothie recipe", schemas)
    top = top_suggestion(ranked)
    assert top is None or top.score < CLASSIFY_THRESHOLD


def test_tie_resolves_to_longest_common_prefix_not_a_leaf():
    schemas = [
        _schema(
            ["Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles", "Corner Profile"],
            naming="Pattern: [Brand] Tile Trim Profile",
            breadcrumb="Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles > Corner Profile",
        ),
        _schema(
            ["Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles", "Transition Profile"],
            naming="Pattern: [Brand] Tile Trim Profile",
            breadcrumb="Floor & Wall Finishes > Tile Accessories > Edge Trims & Profiles > Transition Profile",
        ),
    ]
    ranked = classify_category("aluminium tile trim profile", schemas)

    # Both schemas share the exact top score (identical vocab overlap).
    assert ranked[0].score == ranked[1].score
    top = top_suggestion(ranked)
    assert top.tied_count == 2
    assert top.category_path == [
        "Floor & Wall Finishes", "Tile Accessories", "Edge Trims & Profiles",
    ]
    # It must be the shared family prefix, not either tied leaf.
    assert top.category_path[-1] not in ("Corner Profile", "Transition Profile")
