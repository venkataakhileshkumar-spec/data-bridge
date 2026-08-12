"""
pipeline/quality.py
---------------------
Lightweight data-quality checks over the canonical tables. Each check
returns a list of issue dicts: {source_system, source_id, field, issue}.
These are surfaced in the dashboard as a worklist rather than silently
dropped, since silently dropping records is how population counts quietly
go wrong.
"""

import re

import pandas as pd

NPI_RE = re.compile(r"^\d{10}$")


def _blank(value):
    """True for None, NaN, and empty/whitespace strings."""
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def check_members(raw_df):
    """Runs against the un-deduplicated, per-source-record canonical
    frame (before matching), so every flagged row is traceable to a
    single source record."""
    issues = []
    for _, row in raw_df.iterrows():
        sid = row["source_id"]
        src = row["source_system"]

        if _blank(row.get("last_name")):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "last_name", "issue": "Missing last name"})
        if _blank(row.get("dob")):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "dob", "issue": "Missing or unparseable date of birth"})
        if row.get("sex") not in ("M", "F"):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "sex", "issue": "Missing or unrecognized sex code"})
        pcp = row.get("pcp_npi")
        if not _blank(pcp) and not NPI_RE.match(str(pcp)):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "pcp_npi", "issue": f"PCP NPI '{pcp}' is not a valid 10-digit NPI"})
        if _blank(row.get("city")) or _blank(row.get("state")):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "address", "issue": "Incomplete address (city/state)"})
    return issues


def check_providers(df):
    issues = []
    for _, row in df.iterrows():
        sid = row["source_id"]
        src = row["source_system"]

        if not NPI_RE.match(str(row.get("npi", ""))):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "npi", "issue": f"NPI '{row.get('npi')}' is not a valid 10-digit NPI"})
        if _blank(row.get("specialty")):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "specialty", "issue": "Missing specialty"})
        if _blank(row.get("phone")):
            issues.append({"source_system": src, "source_id": sid,
                            "field": "phone", "issue": "Missing phone number"})
    return issues
