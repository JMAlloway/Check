"""Database models for Check Review Console."""

from app.models.audit import AuditLog, ItemView
from app.models.check import CheckHistory, CheckImage, CheckItem
from app.models.connector import (
    AcknowledgementStatus,
    BankConnectorConfig,
    BatchAcknowledgement,
    BatchStatus,
    CommitBatch,
    CommitDecisionType,
    CommitRecord,
    DeliveryMethod,
    ErrorCategory,
)
from app.models.connector import FileFormat as CommitFileFormat
from app.models.connector import (
    HoldReasonCode,
    ReconciliationReport,
)
from app.models.connector import RecordStatus as CommitRecordStatus
from app.models.decision import Decision, ReasonCode
from app.models.fraud import (
    AmountBucket,
    FraudChannel,
    FraudEvent,
    FraudEventStatus,
    FraudSharedArtifact,
    FraudType,
    MatchSeverity,
    NetworkMatchAlert,
    SharingLevel,
    TenantFraudConfig,
)
from app.models.image_connector import (
    ConnectorAuditLog,
    ConnectorRequestLog,
    ConnectorStatus,
    ImageConnector,
)
from app.models.item_context_connector import (
    FIELD_MAPPING_TEMPLATES,
    ContextConnectorStatus,
)
from app.models.item_context_connector import FileFormat as ContextFileFormat
from app.models.item_context_connector import (
    ImportStatus,
    ItemContextConnector,
    ItemContextImport,
    ItemContextImportRecord,
)
from app.models.item_context_connector import RecordStatus as ContextRecordStatus
from app.models.policy import Policy, PolicyRule, PolicyVersion
from app.models.queue import ApprovalEntitlement, ApprovalEntitlementType, Queue, QueueAssignment
from app.models.user import Permission, Role, User, UserSession

__all__ = [
    "AuditLog",
    "ItemView",
    "CheckItem",
    "CheckImage",
    "CheckHistory",
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
    "CommitRecordStatus",
    "CommitFileFormat",
    "DeliveryMethod",
    "ErrorCategory",
    "AcknowledgementStatus",
    # Connector C (Item Context SFTP)
    "ItemContextConnector",
    "ItemContextImport",
    "ItemContextImportRecord",
    "ContextConnectorStatus",
    "ContextFileFormat",
    "ImportStatus",
    "ContextRecordStatus",
    "FIELD_MAPPING_TEMPLATES",
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
