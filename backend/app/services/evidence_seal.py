"""
Evidence Snapshot Sealing Service.

Provides cryptographic sealing for decision evidence snapshots to ensure
tamper-evidence and chain integrity for bank-grade audit compliance.

Security properties:
1. Tamper-evidence: Any modification to sealed evidence changes the hash
2. Chain integrity: Each evidence links to the previous via hash chain
3. Non-repudiation: Timestamps prove when evidence was sealed
4. Reproducibility: Same content always produces same hash (canonical JSON)
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.decision import Decision
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Current seal algorithm version
SEAL_VERSION = "sha256-v1"


def _canonical_json(data: dict[str, Any]) -> str:
    """
    Convert data to canonical JSON for consistent hashing.

    Canonical form ensures:
    - Sorted keys for deterministic ordering
    - No whitespace for minimal representation
    - UTF-8 encoding
    - Consistent datetime serialization
    """

    def serialize(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [serialize(item) for item in obj]
        return obj

    normalized = serialize(data)
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def compute_evidence_hash(snapshot_data: dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of evidence snapshot content.

    Args:
        snapshot_data: Evidence snapshot dictionary (without seal fields)

    Returns:
        Hex-encoded SHA-256 hash
    """
    # Remove seal fields before hashing (they shouldn't be part of the sealed content)
    content_to_hash = {
        k: v
        for k, v in snapshot_data.items()
        if k not in ("seal_version", "evidence_hash", "previous_evidence_hash", "seal_timestamp")
    }

    canonical = _canonical_json(content_to_hash)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_evidence_hash(snapshot_data: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Verify that evidence snapshot hash matches content.

    Args:
        snapshot_data: Evidence snapshot dictionary with seal fields

    Returns:
        Tuple of (is_valid, error_message)
    """
    stored_hash = snapshot_data.get("evidence_hash")
    if not stored_hash:
        return False, "Evidence snapshot is not sealed (no hash)"

    computed_hash = compute_evidence_hash(snapshot_data)

    if computed_hash != stored_hash:
        return (
            False,
            f"Evidence hash mismatch: stored={stored_hash[:16]}... computed={computed_hash[:16]}...",
        )

    return True, None


async def get_previous_evidence_hash(
    db: AsyncSession,
    check_item_id: str,
    tenant_id: str,
) -> Optional[str]:
    """
    Get the evidence hash from the most recent decision for a check item.

    This enables hash chaining - each new decision's evidence links to
    the previous decision's evidence hash.

    Args:
        db: Database session
        check_item_id: Check item ID
        tenant_id: Tenant ID for security

    Returns:
        Evidence hash of previous decision, or None if first decision
    """
    result = await db.execute(
        select(Decision)
        .where(
            Decision.check_item_id == check_item_id,
            Decision.tenant_id == tenant_id,
        )
        .order_by(Decision.created_at.desc())
        .limit(1)
    )
    previous_decision = result.scalar_one_or_none()

    if previous_decision and previous_decision.evidence_snapshot:
        return previous_decision.evidence_snapshot.get("evidence_hash")

    return None


def seal_evidence_snapshot(
    snapshot_data: dict[str, Any],
    previous_evidence_hash: Optional[str] = None,
) -> dict[str, Any]:
    """
    Seal an evidence snapshot with cryptographic hash.

    Args:
        snapshot_data: Evidence snapshot dictionary
        previous_evidence_hash: Hash from previous decision (for chain)

    Returns:
        Evidence snapshot with seal fields populated
    """
    # Make a copy to avoid mutating input
    sealed = dict(snapshot_data)

    # Set chain link first (it's part of the hashed content)
    sealed["previous_evidence_hash"] = previous_evidence_hash

    # Compute hash of content (excluding seal fields)
    evidence_hash = compute_evidence_hash(sealed)

    # Add seal metadata
    sealed["seal_version"] = SEAL_VERSION
    sealed["evidence_hash"] = evidence_hash
    sealed["seal_timestamp"] = datetime.now(timezone.utc).isoformat()

    return sealed


async def verify_evidence_chain(
    db: AsyncSession,
    check_item_id: str,
    tenant_id: str,
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Verify the entire evidence chain for a check item.

    Checks that:
    1. All evidence snapshots have valid hashes
    2. Each snapshot's previous_evidence_hash matches the prior decision

    Args:
        db: Database session
        check_item_id: Check item ID
        tenant_id: Tenant ID for security

    Returns:
        Tuple of (chain_valid, list of verification results per decision)
    """
    result = await db.execute(
        select(Decision)
        .where(
            Decision.check_item_id == check_item_id,
            Decision.tenant_id == tenant_id,
        )
        .order_by(Decision.created_at.asc())  # Oldest first for chain verification
    )
    decisions = result.scalars().all()

    verification_results = []
    previous_hash = None
    chain_valid = True

    for decision in decisions:
        result_entry = {
            "decision_id": decision.id,
            "created_at": decision.created_at.isoformat() if decision.created_at else None,
            "has_evidence": bool(decision.evidence_snapshot),
            "hash_valid": None,
            "chain_valid": None,
            "error": None,
        }

        if not decision.evidence_snapshot:
            result_entry["error"] = "No evidence snapshot"
            chain_valid = False
        else:
            snapshot = decision.evidence_snapshot

            # Verify hash integrity
            hash_valid, hash_error = verify_evidence_hash(snapshot)
            result_entry["hash_valid"] = hash_valid
            if not hash_valid:
                result_entry["error"] = hash_error
                chain_valid = False

            # Verify chain link
            stored_prev_hash = snapshot.get("previous_evidence_hash")
            if stored_prev_hash != previous_hash:
                result_entry["chain_valid"] = False
                result_entry["error"] = (
                    f"Chain break: expected previous_hash={previous_hash[:16] if previous_hash else 'None'}... "
                    f"got={stored_prev_hash[:16] if stored_prev_hash else 'None'}..."
                )
                chain_valid = False
            else:
                result_entry["chain_valid"] = True

            # Update previous hash for next iteration
            previous_hash = snapshot.get("evidence_hash")

        verification_results.append(result_entry)

    return chain_valid, verification_results
