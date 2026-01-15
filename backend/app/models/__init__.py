"""Database models for Check Review Console."""

from app.models.audit import AuditLog, ItemView
from app.models.check import CheckItem, CheckImage, CheckHistory
from app.models.image_token import ImageAccessToken
from app.models.image_connector import (
    ImageConnector,
    ConnectorAuditLog,
    ConnectorRequestLog,
    ConnectorStatus,
)
from app.models.connector import (
    BankConnectorConfig,
    CommitBatch,
    CommitRecord,
    BatchAcknowledgement,
    ReconciliationReport,
    CommitDecisionType,
    HoldReasonCode,
    BatchStatus,
    RecordStatus,
    FileFormat,
    DeliveryMethod,
    ErrorCategory,
    AcknowledgementStatus,
)
from app.models.decision import Decision, ReasonCode
from app.models.fraud import (
    FraudEvent,
    FraudSharedArtifact,
    NetworkMatchAlert,
    TenantFraudConfig,
    FraudType,
    FraudChannel,
    AmountBucket,
    SharingLevel,
    FraudEventStatus,
    MatchSeverity,
)
from app.models.policy import Policy, PolicyRule, PolicyVersion
from app.models.queue import Queue, QueueAssignment, ApprovalEntitlement, ApprovalEntitlementType
from app.models.user import User, Role, Permission, UserSession

__all__ = [
    "AuditLog",
    "ItemView",
    "CheckItem",
    "CheckImage",
    "CheckHistory",
    "ImageAccessToken",
    # Connector A (Image Connector)
    "ImageConnector",
    "ConnectorAuditLog",
    "ConnectorRequestLog",
    "ConnectorStatus",
    # Connector B (Batch Commit)
    "BankConnectorConfig",
    "CommitBatch",
    "CommitRecord",
    "BatchAcknowledgement",
    "ReconciliationReport",
    "CommitDecisionType",
    "HoldReasonCode",
    "BatchStatus",
    "RecordStatus",
    "FileFormat",
    "DeliveryMethod",
    "ErrorCategory",
    "AcknowledgementStatus",
    # Decision
    "Decision",
    "ReasonCode",
    # Fraud
    "FraudEvent",
    "FraudSharedArtifact",
    "NetworkMatchAlert",
    "TenantFraudConfig",
    "FraudType",
    "FraudChannel",
    "AmountBucket",
    "SharingLevel",
    "FraudEventStatus",
    "MatchSeverity",
    # Policy
    "Policy",
    "PolicyRule",
    "PolicyVersion",
    # Queue
    "Queue",
    "QueueAssignment",
    "ApprovalEntitlement",
    "ApprovalEntitlementType",
    # User
    "User",
    "Role",
    "Permission",
    "UserSession",
]
