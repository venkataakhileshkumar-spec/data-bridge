"""
pipeline/matcher.py
---------------------
Identity resolution: the same person often exists as separate records in
each source system, under different IDs and sometimes with formatting
drift or typos. This module links those records into a single canonical
member and builds a crosswalk (source_system, source_id) -> canonical_id.

Matching strategy (deliberately simple and explainable, not a black box):
  1. Block candidate records together by (date of birth, first name)
     -- an exact, cheap key that dramatically narrows the search space.
  2. Within a block, compare last names with a string-similarity ratio.
     A ratio >= FUZZY_THRESHOLD is treated as the same person (handles
     the occasional typo/truncation), an exact match is marked "exact".
  3. Every record that never finds a match becomes its own canonical
     member (single-source).

This is intentionally transparent so it's easy to audit or replace with
a vendor MDM/identity-resolution product later.
"""

import uuid
from difflib import SequenceMatcher

import pandas as pd

FUZZY_THRESHOLD = 0.82


def _similar(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def resolve_members(df):
    """
    Input: canonical-shaped member rows straight from mapper.py (one row
    per source record, NOT yet deduplicated).
    Output: (matched_df, crosswalk_df)
      matched_df   -- one row per canonical person (deduped, "best" values)
      crosswalk_df -- source_system, source_id, canonical_id, match_type
    """
    df = df.reset_index(drop=True).copy()
    df["_block_key"] = (
        df["dob"].fillna("UNKNOWN") + "|" + df["first_name"].str.lower().fillna("")
    )

    canonical_id_for_row = [None] * len(df)
    match_type_for_row = ["single-source"] * len(df)

    for _, idxs in df.groupby("_block_key").groups.items():
        idxs = list(idxs)
        if len(idxs) == 1:
            canonical_id_for_row[idxs[0]] = str(uuid.uuid4())
            continue

        # Greedy clustering within the block by last-name similarity
        clusters = []  # list of lists of row indices
        for i in idxs:
            placed = False
            for cluster in clusters:
                rep = cluster[0]
                ratio = _similar(df.at[i, "last_name"], df.at[rep, "last_name"])
                if ratio == 1.0 or ratio >= FUZZY_THRESHOLD:
                    cluster.append(i)
                    if ratio < 1.0:
                        match_type_for_row[i] = "fuzzy"
                        match_type_for_row[rep] = "fuzzy"
                    placed = True
                    break
            if not placed:
                clusters.append([i])

        for cluster in clusters:
            cid = str(uuid.uuid4())
            for i in cluster:
                canonical_id_for_row[i] = cid

    df["canonical_id"] = canonical_id_for_row
    df["match_type"] = match_type_for_row

    crosswalk = df[["source_system", "source_id", "canonical_id", "match_type"]].copy()

    # Build one "best" row per canonical_id: prefer the most complete
    # record, and prefer Member Portal values on conflict (assumed to be
    # the more current source) when both are present.
    def pick_best(group):
        group = group.sort_values(
            by="source_system", key=lambda s: s.map({"Member Portal": 0, "Legacy Enrollment System": 1})
        )
        best = group.iloc[0].copy()
        # fill any gaps from other rows in the cluster
        for col in ["first_name", "last_name", "dob", "sex", "plan_type", "pcp_npi", "city", "state"]:
            if pd.isna(best[col]) or best[col] in (None, ""):
                fallback = group[col].dropna()
                fallback = fallback[fallback != ""]
                if len(fallback):
                    best[col] = fallback.iloc[0]
        best["source_systems"] = "|".join(sorted(group["source_system"].unique()))
        best["n_source_records"] = len(group)
        return best

    matched = df.groupby("canonical_id", group_keys=True).apply(pick_best)
    matched.index = matched.index.get_level_values(0)
    matched.index.name = "canonical_id"
    matched = matched.reset_index()
    matched = matched.drop(columns=["_block_key", "match_type"])

    return matched, crosswalk
