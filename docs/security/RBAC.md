# Check Review Console - RBAC Model

This document defines the Role-Based Access Control (RBAC) model for the Check Review Console.

## Overview

The system uses a granular permission model where:
- **Permissions** define specific actions on specific resources
- **Roles** are collections of permissions
- **Users** are assigned one or more roles
- Permissions can have optional **conditions** (e.g., amount limits)

## Permission Structure

Each permission is defined as `resource:action` with an optional conditions JSON.

```
Permission {
  name: string          // Human-readable name
  resource: string      // The entity (check_item, queue, user, etc.)
  action: string        // The operation (view, create, approve, etc.)
  conditions: JSON?     // Optional restrictions (e.g., {"amount_max": 10000})
}
```

## Standard Roles

### 1. Reviewer
**Description:** Day-to-day check processor who reviews items and makes initial decisions.

| Resource | Actions | Conditions |
|----------|---------|------------|
| check_item | view, view_images | - |
| check_item | decide | `amount_max: 5000` (configurable) |
| check_item | add_note, view_history | - |
| queue | view, claim_item | assigned queues only |
| fraud_alert | view | - |
| audit_log | view | own actions only |
| decision | create | non-dual-control items |

**Cannot:**
- Approve items requiring dual control
- Export audit packets
- Manage users or roles
- Configure policies or queues
- Override detection rule decisions without supervisor approval

---

### 2. Approver (Senior Reviewer)
**Description:** Experienced reviewer who can approve dual control items and has elevated limits.

| Resource | Actions | Conditions |
|----------|---------|------------|
| check_item | view, view_images | - |
| check_item | decide | `amount_max: 25000` (configurable) |
| check_item | approve_dual_control | - |
| check_item | override_detection | with justification |
| check_item | add_note, view_history | - |
| queue | view, claim_item, reassign | all queues |
| fraud_alert | view, dismiss | - |
| fraud_event | view | - |
| audit_log | view | team actions |
| decision | create, approve_secondary | - |
| audit_packet | export | - |

**Cannot:**
- Manage users or roles
- Configure policies
- Access admin console

---

### 3. Administrator
**Description:** Full system access including user management and configuration.

| Resource | Actions | Conditions |
|----------|---------|------------|
| check_item | * (all) | - |
| queue | * (all) | - |
| user | view, create, update, deactivate | - |
| role | view, create, update, assign | except system roles |
| policy | view, create, update, activate | - |
| image_connector | view, create, update, test | - |
| fraud_alert | * (all) | - |
| fraud_event | view, create | - |
| audit_log | view, export | all actions |
| audit_packet | export | - |
| system | configure, view_metrics | - |
| reason_code | view, create, update | - |

**Cannot:**
- Delete system roles
- Disable audit logging
- Access other tenants' data

---

### 4. Auditor (Read-Only)
**Description:** Compliance and audit staff with read-only access for examination and review.

| Resource | Actions | Conditions |
|----------|---------|------------|
| check_item | view, view_images, view_history | - |
| queue | view | - |
| user | view | - |
| role | view | - |
| policy | view | - |
| fraud_alert | view | - |
| fraud_event | view | - |
| audit_log | view, export | all actions |
| audit_packet | export | - |
| decision | view | - |

**Cannot:**
- Make any changes
- Process or decide on items
- Claim queue items

---

## Permission Matrix

| Permission | Reviewer | Approver | Admin | Auditor |
|------------|:--------:|:--------:|:-----:|:-------:|
| **Check Items** |
| View check items | ✅ | ✅ | ✅ | ✅ |
| View check images | ✅ | ✅ | ✅ | ✅ |
| View check history | ✅ | ✅ | ✅ | ✅ |
| Decide (within limit) | ✅ | ✅ | ✅ | ❌ |
| Decide (any amount) | ❌ | ❌ | ✅ | ❌ |
| Dual control approval | ❌ | ✅ | ✅ | ❌ |
| Override detection rules | ❌ | ✅ | ✅ | ❌ |
| Add notes | ✅ | ✅ | ✅ | ❌ |
| **Queues** |
| View queues | ✅ | ✅ | ✅ | ✅ |
| Claim items | ✅ | ✅ | ✅ | ❌ |
| Reassign items | ❌ | ✅ | ✅ | ❌ |
| Create/edit queues | ❌ | ❌ | ✅ | ❌ |
| **Fraud** |
| View fraud alerts | ✅ | ✅ | ✅ | ✅ |
| Dismiss fraud alerts | ❌ | ✅ | ✅ | ❌ |
| View fraud events | ❌ | ✅ | ✅ | ✅ |
| Create fraud events | ❌ | ❌ | ✅ | ❌ |
| **Users & Roles** |
| View users | ❌ | ❌ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ✅ | ❌ |
| View roles | ❌ | ❌ | ✅ | ✅ |
| Manage roles | ❌ | ❌ | ✅ | ❌ |
| **Configuration** |
| View policies | ❌ | ❌ | ✅ | ✅ |
| Manage policies | ❌ | ❌ | ✅ | ❌ |
| View connectors | ❌ | ❌ | ✅ | ✅ |
| Manage connectors | ❌ | ❌ | ✅ | ❌ |
| **Audit** |
| View own audit logs | ✅ | ✅ | ✅ | ✅ |
| View all audit logs | ❌ | ✅ | ✅ | ✅ |
| Export audit packets | ❌ | ✅ | ✅ | ✅ |
| Export audit logs | ❌ | ❌ | ✅ | ✅ |

## Conditional Permissions

Some permissions include conditions that further restrict access:

```json
{
  "name": "check_item:decide",
  "conditions": {
    "amount_max": 5000,
    "risk_level_max": "medium",
    "requires_dual_control": false
  }
}
```

### Common Conditions

| Condition | Description | Example |
|-----------|-------------|---------|
| `amount_max` | Maximum check amount | `5000` |
| `amount_min` | Minimum check amount | `0` |
| `risk_level_max` | Maximum risk level allowed | `"medium"` |
| `queue_ids` | Specific queues only | `["queue-1", "queue-2"]` |
| `account_types` | Specific account types | `["consumer", "business"]` |
| `requires_dual_control` | Whether DC items allowed | `false` |

## System Roles

System roles are predefined and cannot be deleted or have permissions removed:

- `system_admin` - Super-user for initial setup
- `reviewer` - Base reviewer role
- `approver` - Base approver role
- `auditor` - Read-only audit role

Custom roles can be created by copying and modifying these templates.

## Multi-Tenant Considerations

- Roles are tenant-specific (except system roles)
- Users can only be assigned roles within their tenant
- Permissions never cross tenant boundaries
- Super-users are tenant-scoped (no cross-tenant access)

## Audit Requirements

All permission checks are logged:
- User ID and username
- Resource and action attempted
- Success/failure
- Timestamp
- IP address
- Conditions evaluated

Failed permission checks generate security alerts after threshold.
