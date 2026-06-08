"""
policy_loader.py
================
Central loader for all Atlas Assurance policy JSON files.

Responsibilities:
  - Load and validate all policy files at server startup via load_all()
  - Cache validated data in memory for fast access by engine modules
  - Provide typed accessor functions — engines NEVER open JSON files directly
  - Raise RuntimeError on any validation failure (prevents server from starting)
  - Support hot-reload via reload() for the /admin/reload-policies endpoint

Policy files are read from:  backend/policies/
Data files are read from:    backend/storage/

Validation Rules (all 7 from the approved implementation plan):
  Rule 1 — Risk weights must sum to 1.0 (±0.001 tolerance)
  Rule 2 — cross_evidence_rules: requires_rules refs must exist as rule_ids
  Rule 3 — severity_definitions: all 4 tiers present, all 5 badge fields per tier
  Rule 4 — cross_evidence_rules: no duplicate rule_id values
  Rule 5 — projects_registry: each project has required fields with correct types
  Rule 6 — All policy files have required _meta fields
  Rule 7 — All required policy files exist and parse as valid JSON

Authors:  Atlas Assurance — Phase 0
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Directory configuration
# ---------------------------------------------------------------------------
_BACKEND_DIR  = Path(__file__).parent
POLICIES_DIR  = _BACKEND_DIR / "policies"
STORAGE_DIR   = _BACKEND_DIR / "storage"

# ---------------------------------------------------------------------------
# Required policy files and their required _meta fields (Rule 6)
# ---------------------------------------------------------------------------
_REQUIRED_POLICY_FILES: dict[str, list[str]] = {
    "severity_definitions.json": ["version"],
    "ncri_scoring.json":         ["version"],
    "context_assumptions.json":  ["version", "effective_date", "source"],
    "risk_weights.json":         ["version", "last_updated", "methodology"],
    "cross_evidence_rules.json": ["version", "rule_count"],
}

_REQUIRED_STORAGE_FILES: dict[str, list[str]] = {
    "projects_registry.json": ["version"],
}

# Required severity tiers and their badge sub-fields (Rule 3)
_REQUIRED_SEVERITY_TIERS  = {"LOW", "MODERATE", "CRITICAL", "FRAUD RISK"}
_REQUIRED_BADGE_FIELDS    = {"label", "color", "bg", "dot", "priority"}

# Required fields per project in projects_registry.json (Rule 5)
_REQUIRED_PROJECT_FIELDS  = {"id", "name", "contractor", "location", "bbox", "baseline_date", "started"}

# In-memory cache
_CACHE: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(filepath: Path) -> Any:
    """
    Load and parse a JSON file.
    Rule 7: raises RuntimeError with actionable message on missing file or parse error.
    """
    if not filepath.exists():
        category = "policies" if filepath.parent == POLICIES_DIR else "storage"
        raise RuntimeError(
            f"[POLICY ERROR] Required policy file not found: {category}/{filepath.name}\n"
            f"  Fix: Create the file before restarting. See implementation plan for schema."
        )
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        category = "policies" if filepath.parent == POLICIES_DIR else "storage"
        raise RuntimeError(
            f"[POLICY ERROR] Failed to parse {category}/{filepath.name} as JSON.\n"
            f"  Error: {exc.msg}\n"
            f"  Line {exc.lineno}, Column {exc.colno}: {exc.doc[max(0,exc.pos-40):exc.pos+40]!r}\n"
            f"  Fix: Validate the file at https://jsonlint.com or run:\n"
            f"       python -c \"import json; json.load(open('{filepath}'))\""
        )


def _validate_meta(data: dict, filename: str, required_fields: list[str]) -> None:
    """
    Rule 6: Validate _meta block exists and contains all required fields.
    """
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        raise RuntimeError(
            f"[POLICY ERROR] policies/{filename}: Missing required '_meta' block.\n"
            f"  Fix: Add a '_meta' object with fields: {required_fields}"
        )
    missing = [f for f in required_fields if f not in meta]
    if missing:
        raise RuntimeError(
            f"[POLICY ERROR] policies/{filename}: Missing required _meta field(s).\n"
            f"  Missing: {missing}\n"
            f"  Fix: Add the missing metadata fields before restarting."
        )


def _validate_severity_definitions(data: dict) -> None:
    """
    Rule 3: badges must have all 4 tiers, each with all 5 sub-fields.
    """
    badges = data.get("badges", {})
    found_keys  = set(badges.keys())
    missing_tiers = _REQUIRED_SEVERITY_TIERS - found_keys
    if missing_tiers:
        raise RuntimeError(
            f"[POLICY ERROR] policies/severity_definitions.json: Incomplete severity definitions.\n"
            f"  Required tiers: {sorted(_REQUIRED_SEVERITY_TIERS)}\n"
            f"  Found: {sorted(found_keys)}\n"
            f"  Missing tiers: {sorted(missing_tiers)}\n"
            f"  Fix: Ensure all four severity tiers are present with all five badge fields."
        )
    for tier in _REQUIRED_SEVERITY_TIERS:
        badge = badges.get(tier, {})
        missing_fields = _REQUIRED_BADGE_FIELDS - set(badge.keys())
        if missing_fields:
            raise RuntimeError(
                f"[POLICY ERROR] policies/severity_definitions.json: Incomplete severity definitions.\n"
                f"  Required tiers: {sorted(_REQUIRED_SEVERITY_TIERS)}\n"
                f"  Found: {sorted(found_keys)}\n"
                f"  Missing tiers: set()\n"
                f"  Missing fields in '{tier}': {sorted(missing_fields)}\n"
                f"  Fix: Ensure all four severity tiers are present with all five badge fields."
            )


def _validate_risk_weights(data: dict) -> None:
    """
    Rule 1: component_weights must sum to 1.0 (±0.001 tolerance).
    """
    weights = data.get("component_weights", {})
    if not weights:
        raise RuntimeError(
            f"[POLICY ERROR] policies/risk_weights.json: 'component_weights' block is missing or empty.\n"
            f"  Fix: Add component_weights dict before restarting."
        )
    actual_sum = sum(weights.values())
    if abs(actual_sum - 1.0) > 0.001:
        raise RuntimeError(
            f"[POLICY ERROR] policies/risk_weights.json: component_weights do not sum to 1.0.\n"
            f"  Current sum: {actual_sum:.4f}\n"
            f"  Weights: {weights}\n"
            f"  Fix: Adjust weights so they sum to exactly 1.0 before restarting."
        )


def _validate_cross_evidence_rules(data: dict) -> None:
    """
    Rule 4: no duplicate rule_id values.
    Rule 2: all requires_rules references must exist as rule_ids.
    Rule 6 (extra): _meta.rule_count must match len(rules).
    """
    rules = data.get("rules", [])
    declared_count = data.get("_meta", {}).get("rule_count")
    actual_count   = len(rules)

    # Rule 6 extension: rule_count match
    if declared_count is not None and declared_count != actual_count:
        raise RuntimeError(
            f"[POLICY ERROR] policies/cross_evidence_rules.json: _meta.rule_count ({declared_count}) "
            f"does not match actual rule count ({actual_count}).\n"
            f"  Fix: Update _meta.rule_count or add/remove rules to match before restarting."
        )

    # Rule 4: duplicate rule_id detection
    all_ids     = [r.get("rule_id") for r in rules]
    seen: set   = set()
    duplicates  = []
    for rid in all_ids:
        if rid in seen:
            duplicates.append(rid)
        seen.add(rid)
    if duplicates:
        raise RuntimeError(
            f"[POLICY ERROR] policies/cross_evidence_rules.json: Duplicate rule_id detected.\n"
            f"  Duplicated ID(s): {duplicates}\n"
            f"  Fix: Assign a unique rule_id to each rule before restarting."
        )

    # Rule 2: requires_rules references must exist
    defined_ids = set(all_ids)
    for rule in rules:
        refs = rule.get("conditions", {}).get("requires_rules", [])
        missing_refs = [r for r in refs if r not in defined_ids]
        if missing_refs:
            raise RuntimeError(
                f"[POLICY ERROR] policies/cross_evidence_rules.json: Rule '{rule.get('rule_id')}' "
                f"requires rule(s) {missing_refs} which do not exist in the rules list.\n"
                f"  Defined rule IDs: {sorted(defined_ids)}\n"
                f"  Fix: Add the missing rules or remove the forward reference before restarting."
            )


def _validate_projects_registry(data: dict) -> None:
    """
    Rule 5: each project must have required fields with correct types.
    """
    projects = data.get("projects", {})
    for project_id, project in projects.items():
        if not isinstance(project, dict):
            raise RuntimeError(
                f"[POLICY ERROR] storage/projects_registry.json: Project '{project_id}' is not a dict.\n"
                f"  Fix: Ensure each project entry is a JSON object."
            )
        missing = _REQUIRED_PROJECT_FIELDS - set(project.keys())
        if missing:
            raise RuntimeError(
                f"[POLICY ERROR] storage/projects_registry.json: Project '{project_id}' is missing required fields.\n"
                f"  Missing: {sorted(missing)}\n"
                f"  Fix: Add the missing fields to this project entry before restarting."
            )
        # Type checks for location and bbox
        loc = project.get("location")
        if not (isinstance(loc, list) and len(loc) == 2 and all(isinstance(x, (int, float)) for x in loc)):
            raise RuntimeError(
                f"[POLICY ERROR] storage/projects_registry.json: Project '{project_id}' has invalid field 'location'.\n"
                f"  Expected: list of 2 numbers [lat, lon]\n"
                f"  Got: {loc!r}"
            )
        bbox = project.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
            raise RuntimeError(
                f"[POLICY ERROR] storage/projects_registry.json: Project '{project_id}' has invalid field 'bbox'.\n"
                f"  Expected: list of 4 numbers [min_lon, min_lat, max_lon, max_lat]\n"
                f"  Got: {bbox!r}"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_all() -> None:
    """
    Load and validate all policy files into the in-memory cache.
    Called once at server startup via @app.on_event("startup").
    Raises RuntimeError on any validation failure — server will not start.

    Validation execution order (matches approved implementation plan):
      1. Rule 7 — file existence check
      2. Rule 7 — JSON parse
      3. Rule 6 — _meta block validation
      4. Rule 3 — severity definitions completeness
      5. Rule 1 — risk weights sum
      6. Rule 4 — duplicate rule_id
      7. Rule 2 — cross-evidence rule references
      8. Rule 5 — projects registry schema
      9. Cache all validated data
    """
    global _CACHE
    raw: dict[str, Any] = {}

    # ── Step 1 & 2: Exist + Parse (Rule 7) ──────────────────────────────────
    for filename in _REQUIRED_POLICY_FILES:
        raw[filename] = _load_json(POLICIES_DIR / filename)

    registry_data = _load_json(STORAGE_DIR / "projects_registry.json")

    # ── Step 3: _meta validation (Rule 6) ────────────────────────────────────
    for filename, required_meta_fields in _REQUIRED_POLICY_FILES.items():
        _validate_meta(raw[filename], filename, required_meta_fields)
    _validate_meta(registry_data, "projects_registry.json", ["version"])

    # ── Step 4: Severity completeness (Rule 3) ────────────────────────────────
    _validate_severity_definitions(raw["severity_definitions.json"])

    # ── Step 5: Risk weights sum (Rule 1) ────────────────────────────────────
    _validate_risk_weights(raw["risk_weights.json"])

    # ── Steps 6 & 7: Cross-evidence rule_id + references (Rules 4 & 2) ───────
    _validate_cross_evidence_rules(raw["cross_evidence_rules.json"])

    # ── Step 8: Projects registry schema (Rule 5) ────────────────────────────
    _validate_projects_registry(registry_data)

    # ── Step 9: Cache ─────────────────────────────────────────────────────────
    _CACHE = {
        "severity_definitions": raw["severity_definitions.json"],
        "ncri_scoring":         raw["ncri_scoring.json"],
        "context_assumptions":  raw["context_assumptions.json"],
        "risk_weights":         raw["risk_weights.json"],
        "cross_evidence_rules": raw["cross_evidence_rules.json"],
        "projects_registry":    registry_data,
    }

    n_projects = len(registry_data.get("projects", {}))
    n_rules    = len(raw["cross_evidence_rules.json"].get("rules", []))
    print(
        f"[policy_loader] All policies loaded and validated OK. "
        f"{n_projects} projects, {n_rules} cross-evidence rules. "
        f"DPR violations/investigation groups deferred to Phase 6."
    )


def reload() -> None:
    """
    Force-reload all policies from disk. Used by POST /admin/reload-policies.
    Validates before replacing the cache — a failed reload leaves the old cache intact.
    """
    # Load into a temporary dict first so a validation failure doesn't corrupt the live cache
    old_cache = _CACHE.copy()
    try:
        _CACHE.clear()
        load_all()
        print("[policy_loader] Hot-reload complete.")
    except RuntimeError:
        _CACHE.update(old_cache)   # restore old cache on failure
        raise


def _require_loaded() -> None:
    """Raise if load_all() has not been called yet (guards accessor misuse)."""
    if not _CACHE:
        raise RuntimeError(
            "[policy_loader] Policies not loaded. Call policy_loader.load_all() first "
            "(should happen automatically via @app.on_event('startup'))."
        )


# ---------------------------------------------------------------------------
# Accessor functions — engines call these, never open JSON directly
# ---------------------------------------------------------------------------

def get_severity_badges() -> dict[str, dict]:
    """Returns badge metadata dict for all 4 severity tiers."""
    _require_loaded()
    return _CACHE["severity_definitions"]["badges"]


def get_severity_thresholds() -> dict:
    """Returns classification thresholds for DPR discrepancy, ELA tampering, ML change score."""
    _require_loaded()
    return _CACHE["severity_definitions"]["thresholds"]


def get_ncri_config() -> dict:
    """Returns deductions, recommended_actions, eligibility_tiers, base_score."""
    _require_loaded()
    return _CACHE["ncri_scoring"]


def get_context_assumptions() -> dict:
    """Returns CPI rate, escalation rates, tolerance bands, context_note_template."""
    _require_loaded()
    return _CACHE["context_assumptions"]


def get_risk_weights() -> dict:
    """Returns component_weights, score_bands, severity_scores."""
    _require_loaded()
    return _CACHE["risk_weights"]


def get_cross_evidence_rules() -> list[dict]:
    """Returns list of all cross-evidence correlation rule dicts."""
    _require_loaded()
    return _CACHE["cross_evidence_rules"]["rules"]


def get_projects_registry() -> dict:
    """Returns the full projects dict keyed by project_id."""
    _require_loaded()
    return _CACHE["projects_registry"]["projects"]
