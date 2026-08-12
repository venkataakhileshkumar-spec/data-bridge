"""
pipeline/sources.py
--------------------
Thin loaders that read each raw source into a pandas DataFrame, keeping
the source's native shape. Normalization happens later in mapper.py --
this module's only job is "get the bytes off disk into a table."
"""

import json
import os

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_legacy_enrollment():
    path = os.path.join(DATA_DIR, "source_legacy_enrollment.csv")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_member_portal():
    path = os.path.join(DATA_DIR, "source_member_portal.json")
    with open(path) as f:
        raw = json.load(f)
    # Flatten the nested JSON (name.first, address.city, etc.) into columns
    return pd.json_normalize(raw)


def load_provider_registry():
    path = os.path.join(DATA_DIR, "source_provider_registry.csv")
    return pd.read_csv(path, dtype=str, keep_default_na=False)
