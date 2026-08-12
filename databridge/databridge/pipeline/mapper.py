"""
pipeline/mapper.py
--------------------
Normalizes each source's native shape into the canonical member and
provider schema. This is the "bridge" part of DataBridge: every source
speaks a different dialect (field names, date formats, coded values),
and this module translates all of them into one consistent shape that
downstream systems (or the rest of this app) can rely on.

Canonical member fields:
    source_system, source_id, first_name, last_name, dob (date),
    sex ("M"/"F"/None), plan_type, pcp_npi, city, state

Canonical provider fields:
    source_system, source_id (=npi here), npi, full_name, specialty,
    practice_name, city, state, phone, accepting_new_patients (bool)
"""

import re
from datetime import datetime

import pandas as pd

PLAN_CODE_MAP = {
    "HMO-100": "HMO",
    "PPO-250": "PPO",
    "MED-ADV-1": "Medicare Advantage",
}


def _parse_legacy_dob(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _parse_iso_dob(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date().isoformat()
    except ValueError:
        return None


def _legacy_addr_city_state(addr_full):
    """'4074 Main St, Clinton, MI' -> ('Clinton', 'MI')"""
    if not addr_full:
        return None, None
    parts = [p.strip() for p in addr_full.split(",")]
    if len(parts) >= 3:
        return parts[-2], parts[-1]
    return None, None


def normalize_legacy_enrollment(df):
    out = pd.DataFrame()
    out["source_system"] = ["Legacy Enrollment System"] * len(df)
    out["source_id"] = df["ENROLL_ID"]
    out["first_name"] = df["MEMB_NAME_FIRST"].str.title()
    out["last_name"] = df["MEMB_NAME_LAST"].str.title()
    out["dob"] = df["DOB"].apply(_parse_legacy_dob)
    out["sex"] = df["SEX_CD"].map({"1": "M", "2": "F"})
    out["plan_type"] = df["PLAN_CD"].map(PLAN_CODE_MAP).fillna(df["PLAN_CD"])
    out["pcp_npi"] = df["PCP_NPI"].replace("", None)
    city_state = df["ADDR_FULL"].apply(_legacy_addr_city_state)
    out["city"] = [cs[0] for cs in city_state]
    out["state"] = [cs[1] for cs in city_state]
    return out


def normalize_member_portal(df):
    out = pd.DataFrame()
    out["source_system"] = ["Member Portal"] * len(df)
    out["source_id"] = df["memberId"]
    out["first_name"] = df.get("name.first", "").fillna("")
    out["last_name"] = df.get("name.last", "").fillna("")
    out["dob"] = df["dateOfBirth"].apply(_parse_iso_dob)
    out["sex"] = df["sex"].map({"Male": "M", "Female": "F", "M": "M", "F": "F"})
    out["plan_type"] = df["planType"]
    out["pcp_npi"] = df.get("primaryCareProviderNpi")
    out["city"] = df.get("address.city")
    out["state"] = df.get("address.state")
    return out


def normalize_provider_registry(df):
    out = pd.DataFrame()
    out["source_system"] = ["Provider Registry"] * len(df)
    out["source_id"] = df["NPI"]
    out["npi"] = df["NPI"]
    out["full_name"] = df["PROVIDER_NAME"]
    out["specialty"] = df["SPECIALTY"]
    out["practice_name"] = df["PRACTICE"]
    addr_parts = df["ADDRESS"].apply(_legacy_addr_city_state)
    out["city"] = [p[0] for p in addr_parts]
    out["state"] = [p[1] for p in addr_parts]
    out["phone"] = df["PHONE"]
    out["accepting_new_patients"] = df["ACCEPTING_NEW_PATIENTS"] == "Y"
    return out


def build_canonical_members():
    """Loads both member sources and returns them normalized, unmatched
    (one row per source record -- deduplication happens in matcher.py)."""
    from . import sources
    legacy = normalize_legacy_enrollment(sources.load_legacy_enrollment())
    portal = normalize_member_portal(sources.load_member_portal())
    combined = pd.concat([legacy, portal], ignore_index=True)
    return combined


def build_canonical_providers():
    from . import sources
    return normalize_provider_registry(sources.load_provider_registry())
