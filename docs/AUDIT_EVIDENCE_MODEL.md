# Audit & Evidence Integrity Model

> **Purpose**: Document how decisions are captured, sealed, and verified for audit replay
> **Audience**: Internal Auditors, Examiners, Compliance Officers, InfoSec
> **Key Differentiator**: Cryptographic tamper-evidence for bank-grade compliance

---

## Why Evidence Snapshots Matter

When a reviewer makes a decision, they see:
- Check image
- Account balances
- Risk flags
- Policy evaluation results
- AI-generated insights (if any)

**Six months later, an auditor asks: "What exactly did the reviewer see?"**

Without evidence snapshots, you're left reconstructing from:
- Database records that may have changed
- Policy versions that may have been updated
- Account balances that have definitely changed

**Evidence snapshots capture the exact state at decision time.**

---

## Evidence Snapshot Structure

```json
{
  "snapshot_version": "1.0",
  "captured_at": "2026-01-15T14:32:15.123Z",

  "check_context": {
    "amount": "4532.00",
    "account_type": "CHECKING",
    "account_tenure_days": 847,
    "current_balance": "12453.21",
    "average_balance_30d": "8234.50",
    "returned_item_count_90d": 0,
    "risk_level": "MEDIUM",
    "risk_flags": ["large_amount", "new_payee"]
  },

  "images": [
    {
      "id": "img-123",
      "image_type": "front",
      "content_hash": "sha256:a1b2c3..."
    },
    {
      "id": "img-124",
      "image_type": "back",
      "content_hash": "sha256:d4e5f6..."
    }
  ],

  "policy_evaluation": {
    "policy_version_id": "pol-v-456",
    "rules_triggered": ["high_amount_review", "new_payee_flag"],
    "requires_dual_control": true,
    "risk_score": 0.72
  },

  "ai_context": {
    "ai_assisted": true,
    "model_id": "fraud-detection-v2.3",
    "ai_risk_score": "0.68",
    "flags_displayed": [
      {"code": "UNUSUAL_AMOUNT", "confidence": 0.82}
    ],
    "flags_reviewed": ["UNUSUAL_AMOUNT"]
  },

  "seal_version": "sha256-v1",
  "evidence_hash": "sha256:7f8e9d...",
  "previous_evidence_hash": "sha256:1a2b3c...",
  "seal_timestamp": "2026-01-15T14:32:15.456Z"
}
```

---

## Cryptographic Seal

### What Gets Sealed

The evidence hash is computed over:
- `snapshot_version`
- `captured_at`
- `check_context` (all fields)
- `images` (references and content hashes)
- `policy_evaluation` (all fields)
- `ai_context` (all fields)
- `decision_context` (additional metadata)
- `previous_evidence_hash` (chain link)

**The seal fields themselves (`seal_version`, `evidence_hash`, `seal_timestamp`) are NOT included in the hash.**

### Hashing Algorithm

```python
def compute_evidence_hash(snapshot_data):
    # 1. Remove seal fields
    content = {k: v for k, v in snapshot_data.items()
               if k not in ('seal_version', 'evidence_hash',
                           'previous_evidence_hash', 'seal_timestamp')}

    # 2. Canonical JSON (sorted keys, no whitespace)
    canonical = json.dumps(content, sort_keys=True, separators=(',', ':'))

    # 3. SHA-256 hash
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
```

### Why Canonical JSON?

The same data must always produce the same hash. Canonical JSON ensures:
- Keys are sorted alphabetically
- No optional whitespace
- Consistent datetime format (ISO 8601)
- Deterministic across all implementations

---

## Hash Chain Integrity

Each decision's evidence links to the previous decision for the same check item.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HASH CHAIN                                   │
│                                                                      │
│  Decision 1            Decision 2            Decision 3              │
│  (Initial Review)      (Escalation)          (Final Approval)        │
│                                                                      │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐        │
│  │ evidence_hash │    │ evidence_hash │    │ evidence_hash │        │
│  │   = H(D1)     │◄───│   = H(D2)     │◄───│   = H(D3)     │        │
│  │               │    │               │    │               │        │
│  │ prev_hash     │    │ prev_hash     │    │ prev_hash     │        │
│  │   = null      │    │   = H(D1)     │    │   = H(D2)     │        │
│  └───────────────┘    └───────────────┘    └───────────────┘        │
│                                                                      │
│  Tampering D1 content → H(D1) changes → D2.prev_hash mismatch       │
└─────────────────────────────────────────────────────────────────────┘
```

### Chain Verification

```python
def verify_chain(decisions):
    previous_hash = None

    for decision in sorted(decisions, key=lambda d: d.created_at):
        snapshot = decision.evidence_snapshot

        # 1. Verify snapshot hash
        computed = compute_evidence_hash(snapshot)
        if computed != snapshot['evidence_hash']:
            return False, "Hash mismatch - content tampered"

        # 2. Verify chain link
        if snapshot['previous_evidence_hash'] != previous_hash:
            return False, "Chain broken - ordering tampered"

        previous_hash = snapshot['evidence_hash']

    return True, "Chain verified"
```

---

## Audit Capabilities

### 1. Decision Replay

**Question**: "What did the reviewer see when they approved check #12345?"

**Answer**: Query the decision record, retrieve the evidence snapshot, display exactly what was shown.

```
GET /api/v1/decisions/{check_item_id}/history

Response:
[
  {
    "decision_id": "dec-789",
    "action": "APPROVE",
    "user": "jane.reviewer",
    "timestamp": "2026-01-15T14:32:15Z",
    "evidence_snapshot": { ... complete state ... }
  }
]
```

### 2. Chain Verification

**Question**: "Has any decision evidence been modified?"

**Answer**: Run chain verification endpoint.

```
GET /api/v1/decisions/{check_item_id}/verify-evidence-chain

Response:
{
  "check_item_id": "chk-123",
  "chain_valid": true,
  "total_decisions": 3,
  "verification_results": [
    {"decision_id": "dec-1", "hash_valid": true, "chain_valid": true},
    {"decision_id": "dec-2", "hash_valid": true, "chain_valid": true},
    {"decision_id": "dec-3", "hash_valid": true, "chain_valid": true}
  ]
}
```

### 3. Policy Compliance

**Question**: "Was dual control enforced for items over $5,000?"

**Answer**: Query decisions where amount > 5000, verify `requires_dual_control` in policy_evaluation, verify `dual_control_approver_id` is set.

### 4. AI Override Tracking

**Question**: "How often do reviewers override AI recommendations?"

**Answer**: Compare `ai_context.ai_recommendation` with decision `action`.

---

## Audit Trail Components

### Event Types Logged

| Event | Data Captured | Retention |
|-------|---------------|-----------|
| **Decision Made** | user, action, reason codes, evidence_hash | 7 years |
| **Dual Control** | original_reviewer, approver, timestamps | 7 years |
| **AI Recommendation** | model_id, recommendation, user_action | 7 years |
| **Image Access** | user, image_id, timestamp, correlation_id | 7 years |
| **Login/Logout** | user, IP, timestamp, success/failure | 2 years |
| **Permission Change** | admin, target_user, before/after | 7 years |

### Log Format

```json
{
  "timestamp": "2026-01-15T14:32:15.123Z",
  "event_type": "decision_made",
  "tenant_id": "tenant-456",
  "user_id": "user-123",
  "username": "jane.reviewer",
  "check_item_id": "chk-789",
  "action": "APPROVE",
  "evidence_hash": "sha256:7f8e9d...",
  "ip_address": "192.168.1.100",
  "correlation_id": "corr-abc123"
}
```

### Log Immutability

Audit logs are written to append-only storage:
- Cannot be deleted within retention period
- Cannot be modified after write
- Archived to cold storage after 90 days
- Retrievable for examination on request

---

## Compliance Mapping

| Requirement | How We Address It |
|-------------|-------------------|
| **FFIEC - Dual Control** | Policy-driven dual control, evidence of both approvals |
| **SOC 2 CC7.1 - Monitoring** | Complete audit trail of all decisions |
| **GLBA - Audit Trail** | 7-year retention, tamper-evident |
| **OCC - Decision Documentation** | Evidence snapshots capture complete context |
| **Bank Examiner Review** | Chain verification proves integrity |

---

## Examiner Access

### What Examiners Can Request

| Request | How to Fulfill |
|---------|----------------|
| "Show me decisions for date range X" | Query by date, export with evidence |
| "Verify no decisions were modified" | Run chain verification |
| "Show dual control compliance" | Query high-value decisions, show approver chain |
| "Export audit logs for review" | Export in standard format (JSON, CSV) |

### Export Formats

```
# Full decision export with evidence
GET /api/v1/admin/export/decisions?start=2026-01-01&end=2026-01-31

# Audit log export
GET /api/v1/admin/export/audit-logs?start=2026-01-01&end=2026-01-31

# Chain verification report
GET /api/v1/admin/report/evidence-integrity
```

---

## Evidence Retention

| Data Type | Retention | Justification |
|-----------|-----------|---------------|
| Evidence snapshots | 7 years | Regulatory requirement |
| Audit logs | 7 years | Regulatory requirement |
| Check images | Bank-controlled | Stored on bank systems |
| User session logs | 2 years | Security investigation |

### Deletion Process

Evidence cannot be deleted before retention period expires.

After retention period:
1. Scheduled job identifies expired records
2. Records marked for deletion (soft delete)
3. 30-day grace period for recovery
4. Permanent deletion with audit log entry

---

## Implementation Details

### Sealing Process

```
1. Reviewer submits decision
2. System captures evidence snapshot
   - Current check context from database
   - Image references (not images themselves)
   - Policy evaluation result
   - AI context (if applicable)
3. System retrieves previous evidence hash (if any)
4. System computes SHA-256 of canonical snapshot
5. System stores sealed snapshot with decision
6. Audit log entry created
7. Transaction committed
```

### Verification Process

```
1. Query all decisions for check item
2. Sort by creation timestamp
3. For each decision:
   a. Recompute hash from snapshot content
   b. Compare to stored evidence_hash
   c. Verify previous_evidence_hash matches prior decision
4. Report any mismatches
```

---

## Failure Scenarios

### What if evidence hash doesn't match?

**Implication**: Snapshot content was modified after sealing.

**Investigation**:
1. Compare stored content vs expected
2. Check database modification logs
3. Identify when/how modification occurred
4. Escalate to security team

### What if chain link doesn't match?

**Implication**: Decision ordering was tampered, or a decision was inserted/deleted.

**Investigation**:
1. Compare expected vs actual chain
2. Identify missing or unexpected links
3. Review database transaction logs
4. Escalate to security team

### What if snapshot is missing?

**Implication**: Decision was created without evidence capture (bug or manipulation).

**Investigation**:
1. Review decision creation logs
2. Check for system errors at decision time
3. Determine if this is a code bug or tampering

---

## Frequently Asked Questions

### "Can I regenerate evidence for old decisions?"

**No.** Evidence captures state at decision time. Regenerating would capture current state, defeating the purpose.

### "What if the image changes after the decision?"

The evidence snapshot contains the image's content hash at decision time. If the image changes, the hash in the snapshot won't match the current image — proving the image was modified.

### "Can an admin modify evidence?"

**No.** Evidence is written as part of the decision transaction. There is no API to modify evidence after creation. Direct database modification would be detected by hash chain verification.

### "How do we prove evidence wasn't tampered?"

Run the chain verification endpoint. If all hashes match and the chain is unbroken, tampering has not occurred (or is computationally infeasible).

---

*Document Version: 1.0 | Last Updated: January 2026*
