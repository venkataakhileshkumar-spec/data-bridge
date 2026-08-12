"""
DataBridge — base project
===========================
A small integration pipeline for member & provider data that ingests
records from differently-shaped source systems (a legacy CSV enrollment
extract and a JSON member-portal export, plus a provider registry CSV),
normalizes them into one canonical schema, resolves duplicate member
identities across sources, and flags data-quality issues -- all served
through a Flask API and a pipeline-status dashboard.

Run:
    pip install -r requirements.txt
    python generate_source_data.py     # creates synthetic multi-source data
    python app.py
    open http://127.0.0.1:5001
"""

from flask import Flask, jsonify, render_template

from pipeline import mapper, matcher, quality

app = Flask(__name__)

_cache = {}


def run_pipeline():
    """Runs the full ingest -> normalize -> match -> quality-check flow
    and caches the results in memory. Re-run by restarting the app or
    calling /api/pipeline/run."""
    raw_members = mapper.build_canonical_members()
    matched_members, crosswalk = matcher.resolve_members(raw_members)
    providers = mapper.build_canonical_providers()

    member_issues = quality.check_members(raw_members)
    provider_issues = quality.check_providers(providers)

    _cache["raw_members"] = raw_members
    _cache["matched_members"] = matched_members
    _cache["crosswalk"] = crosswalk
    _cache["providers"] = providers
    _cache["member_issues"] = member_issues
    _cache["provider_issues"] = provider_issues
    return _cache


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/pipeline/run", methods=["POST", "GET"])
def api_run_pipeline():
    run_pipeline()
    return jsonify({"status": "ok"})


def _ensure_cache():
    if not _cache:
        run_pipeline()
    return _cache


@app.route("/api/pipeline/summary")
def api_summary():
    c = _ensure_cache()
    raw = c["raw_members"]
    matched = c["matched_members"]
    crosswalk = c["crosswalk"]

    sources = raw["source_system"].value_counts().to_dict()
    exact_matches = int((crosswalk["match_type"] == "single-source").sum())
    fuzzy_matches = int((crosswalk["match_type"] == "fuzzy").sum())
    linked_people = int((matched["n_source_records"] > 1).sum())

    return jsonify({
        "sources_connected": raw["source_system"].nunique() + 1,  # + provider registry
        "raw_records_ingested": int(len(raw)) + int(len(c["providers"])),
        "canonical_members": int(len(matched)),
        "canonical_providers": int(len(c["providers"])),
        "linked_people": linked_people,
        "records_by_source": sources,
        "quality_issues": len(c["member_issues"]) + len(c["provider_issues"]),
        "member_quality_issues": len(c["member_issues"]),
        "provider_quality_issues": len(c["provider_issues"]),
    })


@app.route("/api/pipeline/flow")
def api_flow():
    """Counts feeding the source -> bridge -> canonical flow diagram."""
    c = _ensure_cache()
    raw = c["raw_members"]
    by_source = raw["source_system"].value_counts().to_dict()
    return jsonify({
        "legacy_records": int(by_source.get("Legacy Enrollment System", 0)),
        "portal_records": int(by_source.get("Member Portal", 0)),
        "provider_records": int(len(c["providers"])),
        "canonical_members": int(len(c["matched_members"])),
        "canonical_providers": int(len(c["providers"])),
        "linked_people": int((c["matched_members"]["n_source_records"] > 1).sum()),
    })


@app.route("/api/members")
def api_members():
    c = _ensure_cache()
    df = c["matched_members"]
    cols = ["canonical_id", "first_name", "last_name", "dob", "sex",
            "plan_type", "pcp_npi", "city", "state", "source_systems", "n_source_records"]
    return jsonify(df[cols].head(50).to_dict(orient="records"))


@app.route("/api/providers")
def api_providers():
    c = _ensure_cache()
    df = c["providers"]
    cols = ["npi", "full_name", "specialty", "practice_name", "city",
            "state", "phone", "accepting_new_patients"]
    return jsonify(df[cols].head(50).to_dict(orient="records"))


@app.route("/api/crosswalk")
def api_crosswalk():
    c = _ensure_cache()
    df = c["crosswalk"]
    linked_ids = df["canonical_id"].value_counts()
    linked_ids = linked_ids[linked_ids > 1].index
    sample = df[df["canonical_id"].isin(linked_ids)].sort_values("canonical_id").head(60)
    return jsonify(sample.to_dict(orient="records"))


@app.route("/api/quality-issues")
def api_quality_issues():
    c = _ensure_cache()
    issues = c["member_issues"] + c["provider_issues"]
    return jsonify(issues[:100])


if __name__ == "__main__":
    run_pipeline()
    app.run(debug=False, port=5001)
