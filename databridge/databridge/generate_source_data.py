"""
generate_source_data.py
------------------------
Creates synthetic data for two DIFFERENTLY-SHAPED source systems, which is
the whole reason DataBridge exists: real organizations end up with member
and provider data split across a legacy enrollment system, a newer member
portal, and a provider registry -- each with its own field names, formats,
and quirks. This script fabricates that mess on purpose so the bridge/
pipeline has real normalization work to do.

No real member or provider data is used anywhere in this project.

Run:
    python generate_source_data.py

Output:
    data/source_legacy_enrollment.csv    (Legacy Enrollment System, CSV)
    data/source_member_portal.json       (Member Portal, JSON)
    data/source_provider_registry.csv    (Provider Registry, CSV)
"""

import csv
import json
import random
from datetime import date, timedelta

random.seed(7)

FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Linda", "David",
               "Barbara", "Michael", "Elizabeth", "Sara", "Anita", "Kevin",
               "Priya", "Wei", "Carlos", "Fatima", "Noah", "Emma", "Liam"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
              "Miller", "Davis", "Rodriguez", "Martinez", "Chen", "Patel",
              "Kim", "Nguyen", "Khan", "Silva", "Anderson", "Clark"]
SPECIALTIES = ["Family Medicine", "Internal Medicine", "Cardiology",
               "Endocrinology", "Pediatrics", "Behavioral Health",
               "Orthopedics", "OB/GYN", "Dermatology"]
CITIES = [("Springfield", "IL"), ("Fairview", "TX"), ("Georgetown", "OH"),
          ("Riverside", "CA"), ("Franklin", "NC"), ("Clinton", "MI")]

N_MEMBERS = 600            # members that exist independently in each source
N_OVERLAP = 180            # members present in BOTH sources (need matching)
N_PROVIDERS = 90


def random_dob(min_age=0, max_age=90):
    age = random.randint(min_age, max_age)
    d = date.today() - timedelta(days=age * 365 + random.randint(0, 364))
    return d


def npi():
    """Fabricated 10-digit NPI-shaped identifier (not a real NPI)."""
    return "1" + "".join(str(random.randint(0, 9)) for _ in range(9))


def make_person():
    return {
        "first": random.choice(FIRST_NAMES),
        "last": random.choice(LAST_NAMES),
        "dob": random_dob(),
        "sex": random.choice(["M", "F"]),
    }


def legacy_row(person, member_num, mangled=False):
    """
    Legacy Enrollment System: all-caps names, MM/DD/YYYY dates,
    a single concatenated address field, sex coded 1/2.
    """
    first, last = person["first"].upper(), person["last"].upper()
    if mangled and random.random() < 0.3:
        # simulate a data-entry typo in ~30% of overlap records
        last = last[:-1] if len(last) > 3 else last
    city, state = random.choice(CITIES)
    return {
        "ENROLL_ID": f"LEG-{member_num:06d}",
        "MEMB_NAME_LAST": last,
        "MEMB_NAME_FIRST": first,
        "DOB": person["dob"].strftime("%m/%d/%Y"),
        "SEX_CD": "1" if person["sex"] == "M" else "2",
        "ADDR_FULL": f"{random.randint(100,9999)} Main St, {city}, {state}",
        "PLAN_CD": random.choice(["HMO-100", "PPO-250", "MED-ADV-1"]),
        "PCP_NPI": npi() if random.random() < 0.85 else "",
    }


def portal_row(person, member_num, source_id_offset=0):
    """
    Member Portal: proper-case names, ISO dates, structured address,
    sex as full word.
    """
    city, state = random.choice(CITIES)
    return {
        "memberId": f"PORTAL-{member_num + source_id_offset:06d}",
        "name": {"first": person["first"], "last": person["last"]},
        "dateOfBirth": person["dob"].isoformat(),
        "sex": "Male" if person["sex"] == "M" else "Female",
        "address": {
            "line1": f"{random.randint(100,9999)} Main St",
            "city": city, "state": state,
        },
        "planType": random.choice(["HMO", "PPO", "Medicare Advantage"]),
        "primaryCareProviderNpi": npi() if random.random() < 0.9 else None,
    }


def provider_row(i):
    first, last = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
    city, state = random.choice(CITIES)
    return {
        "NPI": npi(),
        "PROVIDER_NAME": f"{last}, {first} MD",
        "SPECIALTY": random.choice(SPECIALTIES),
        "PRACTICE": f"{last} {random.choice(['Medical Group', 'Clinic', 'Health Partners'])}",
        "ADDRESS": f"{random.randint(100,9999)} Health Way, {city}, {state}",
        "PHONE": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
        "ACCEPTING_NEW_PATIENTS": random.choice(["Y", "N"]),
    }


def build():
    legacy_rows, portal_rows = [], []

    # Overlapping members: same person appears in BOTH sources (the
    # matching problem DataBridge needs to solve), sometimes with a
    # typo or formatting drift.
    for i in range(N_OVERLAP):
        person = make_person()
        legacy_rows.append(legacy_row(person, i, mangled=True))
        portal_rows.append(portal_row(person, i))

    # Members that exist ONLY in the legacy system
    for i in range(N_OVERLAP, N_OVERLAP + N_MEMBERS // 2):
        legacy_rows.append(legacy_row(make_person(), i))

    # Members that exist ONLY in the portal
    for i in range(N_OVERLAP, N_OVERLAP + N_MEMBERS // 2):
        portal_rows.append(portal_row(make_person(), i, source_id_offset=100000))

    # A few intentionally messy rows: missing DOB, blank name -- exercises
    # the data-quality checks.
    for i in range(5):
        bad = legacy_row(make_person(), 900000 + i)
        bad["DOB"] = ""
        legacy_rows.append(bad)
    for i in range(5):
        bad = portal_row(make_person(), 900000 + i)
        bad["name"]["last"] = ""
        portal_rows.append(bad)

    random.shuffle(legacy_rows)
    random.shuffle(portal_rows)

    providers = [provider_row(i) for i in range(N_PROVIDERS)]

    return legacy_rows, portal_rows, providers


def write_legacy_csv(rows, path):
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_portal_json(rows, path):
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)


def write_provider_csv(rows, path):
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    legacy_rows, portal_rows, providers = build()
    write_legacy_csv(legacy_rows, "data/source_legacy_enrollment.csv")
    write_portal_json(portal_rows, "data/source_member_portal.json")
    write_provider_csv(providers, "data/source_provider_registry.csv")
    print(f"Legacy Enrollment System: {len(legacy_rows)} rows -> data/source_legacy_enrollment.csv")
    print(f"Member Portal:           {len(portal_rows)} rows -> data/source_member_portal.json")
    print(f"Provider Registry:       {len(providers)} rows -> data/source_provider_registry.csv")
    print(f"(~{N_OVERLAP} members appear in both member sources under different IDs -- "
          f"that's the matching problem the bridge resolves.)")
