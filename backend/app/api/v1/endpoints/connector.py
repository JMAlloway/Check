"""Connector B - Batch Commit API Endpoints.

Bank-auditable endpoints for:
- Bank configuration management
- Batch creation and approval (dual control)
- File generation and download
- Acknowledgement processing
- Reconciliation reporting
- Failed record resolution

All operations require authentication and appropriate permissions.
No direct core writes - files are picked up by bank middleware.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_permission
from app.audit.service import AuditService
from app.models.audit import AuditAction
from app.models.connector import (
    BankConnectorConfig,
    BatchAcknowledgement,
    BatchStatus,
    CommitBatch,
    CommitDecisionType,
    CommitRecord,
    ReconciliationReport,
    RecordStatus,
)
from app.schemas.connector import (
    AcknowledgementRequest,
    AcknowledgementResponse,
    BankConnectorConfigCreate,
    BankConnectorConfigResponse,
    BankConnectorConfigUpdate,
    BatchApprovalRequest,
    BatchCancelRequest,
    BatchConfirmationDialog,
    BatchCreateRequest,
    BatchFileResponse,
    BatchResponse,
    BatchSummary,
    ConnectorDashboard,
    ReconciliationReportRequest,
    ReconciliationReportResponse,
    RecordResolutionRequest,
    RecordSummary,
)
from app.services.connector_service import (
    BatchNotFoundError,
    BatchStateError,
    ConnectorError,
    ConnectorService,
    DualControlViolation,
    FileGenerationError,
)

router = APIRouter()


# =============================================================================
# BANK CONFIGURATION ENDPOINTS
# =============================================================================


@router.get("/configs", response_model=list[BankConnectorConfigResponse])
async def list_bank_configs(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
    include_inactive: bool = False,
):
    """List bank connector configurations."""
    query = select(BankConnectorConfig).where(
        BankConnectorConfig.tenant_id == current_user.tenant_id
    )

    if not include_inactive:
        query = query.where(BankConnectorConfig.is_active == True)

    query = query.order_by(BankConnectorConfig.bank_name)
    result = await db.execute(query)
    configs = result.scalars().all()

    return [
        BankConnectorConfigResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            bank_id=c.bank_id,
            bank_name=c.bank_name,
            is_active=c.is_active,
            file_format=c.file_format,
            file_encoding=c.file_encoding,
            file_line_ending=c.file_line_ending,
            file_name_pattern=c.file_name_pattern,
            field_config=c.field_config,
            delivery_method=c.delivery_method,
            expects_acknowledgement=c.expects_acknowledgement,
            ack_timeout_hours=c.ack_timeout_hours,
            ack_file_pattern=c.ack_file_pattern,
            require_encryption=c.require_encryption,
            max_records_per_file=c.max_records_per_file,
            include_header_row=c.include_header_row,
            include_trailer_row=c.include_trailer_row,
            include_checksum=c.include_checksum,
            include_notes=c.include_notes,
            max_notes_length=c.max_notes_length,
            created_by_user_id=c.created_by_user_id,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.post(
    "/configs", response_model=BankConnectorConfigResponse, status_code=status.HTTP_201_CREATED
)
async def create_bank_config(
    request: Request,
    config_data: BankConnectorConfigCreate,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "admin"))],
):
    """Create a new bank connector configuration."""
    # Check for duplicate bank_id
    existing = await db.execute(
        select(BankConnectorConfig).where(
            BankConnectorConfig.tenant_id == current_user.tenant_id,
            BankConnectorConfig.bank_id == config_data.bank_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bank configuration already exists for bank_id: {config_data.bank_id}",
        )

    config = BankConnectorConfig(
        tenant_id=current_user.tenant_id,
        bank_id=config_data.bank_id,
        bank_name=config_data.bank_name,
        file_format=config_data.file_format,
        file_encoding=config_data.file_encoding,
        file_line_ending=config_data.file_line_ending,
        file_name_pattern=config_data.file_name_pattern,
        field_config=config_data.field_config.model_dump(),
        delivery_method=config_data.delivery_method,
        delivery_config=config_data.delivery_config,
        expects_acknowledgement=config_data.expects_acknowledgement,
        ack_timeout_hours=config_data.ack_timeout_hours,
        ack_file_pattern=config_data.ack_file_pattern,
        require_encryption=config_data.require_encryption,
        pgp_key_id=config_data.pgp_key_id,
        max_records_per_file=config_data.max_records_per_file,
        include_header_row=config_data.include_header_row,
        include_trailer_row=config_data.include_trailer_row,
        include_checksum=config_data.include_checksum,
        include_notes=config_data.include_notes,
        max_notes_length=config_data.max_notes_length,
        created_by_user_id=current_user.id,
    )
    db.add(config)
    await db.flush()

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.CREATE,
        resource_type="bank_connector_config",
        resource_id=config.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Created bank connector config: {config.bank_name}",
        metadata={"bank_id": config.bank_id},
    )

    # Explicit commit for write operation
    await db.commit()

    return BankConnectorConfigResponse(
        id=config.id,
        tenant_id=config.tenant_id,
        bank_id=config.bank_id,
        bank_name=config.bank_name,
        is_active=config.is_active,
        file_format=config.file_format,
        file_encoding=config.file_encoding,
        file_line_ending=config.file_line_ending,
        file_name_pattern=config.file_name_pattern,
        field_config=config.field_config,
        delivery_method=config.delivery_method,
        expects_acknowledgement=config.expects_acknowledgement,
        ack_timeout_hours=config.ack_timeout_hours,
        ack_file_pattern=config.ack_file_pattern,
        require_encryption=config.require_encryption,
        max_records_per_file=config.max_records_per_file,
        include_header_row=config.include_header_row,
        include_trailer_row=config.include_trailer_row,
        include_checksum=config.include_checksum,
        include_notes=config.include_notes,
        max_notes_length=config.max_notes_length,
        created_by_user_id=config.created_by_user_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


# =============================================================================
# BATCH ENDPOINTS
# =============================================================================


@router.get("/batches", response_model=list[BatchSummary])
async def list_batches(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
    status_filter: BatchStatus | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List commit batches."""
    connector = ConnectorService(db)
    batches, _ = await connector.list_batches(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return [
        BatchSummary(
            id=b.id,
            batch_number=b.batch_number,
            status=b.status,
            total_records=b.total_records,
            total_amount=b.total_amount,
            release_count=b.release_count,
            hold_count=b.hold_count,
            return_count=b.return_count,
            reject_count=b.reject_count,
            escalate_count=b.escalate_count,
            has_high_risk_items=b.has_high_risk_items,
            high_risk_count=b.high_risk_count,
            created_at=b.created_at,
            created_by_user_id=b.created_by_user_id,
            approved_at=b.approved_at,
            approver_user_id=b.approver_user_id,
            file_generated_at=b.file_generated_at,
            transmitted_at=b.transmitted_at,
            ack_status=b.ack_status,
        )
        for b in batches
    ]


@router.post("/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    request: Request,
    batch_data: BatchCreateRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "create"))],
):
    """
    Create a new commit batch from approved decisions.

    All decisions must have dual control approval.
    The batch itself requires separate approval before file generation.
    """
    connector = ConnectorService(db)

    try:
        batch = await connector.create_batch(
            tenant_id=current_user.tenant_id,
            bank_config_id=batch_data.bank_config_id,
            decision_ids=batch_data.decision_ids,
            user_id=current_user.id,
            description=batch_data.description,
        )
    except DualControlViolation as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ConnectorError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.CREATE,
        resource_type="commit_batch",
        resource_id=batch.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Created commit batch: {batch.batch_number}",
        metadata={
            "total_records": batch.total_records,
            "total_amount": str(batch.total_amount),
        },
    )

    return _batch_to_response(batch)


@router.get("/batches/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
    include_records: bool = True,
):
    """Get batch details."""
    connector = ConnectorService(db)

    try:
        batch = await connector.get_batch(batch_id)
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # Verify tenant access
    if batch.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    return _batch_to_response(batch, include_records=include_records)


@router.get("/batches/{batch_id}/confirmation", response_model=BatchConfirmationDialog)
async def get_batch_confirmation(
    batch_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "approve"))],
):
    """Get batch confirmation dialog data before approval."""
    connector = ConnectorService(db)

    try:
        batch = await connector.get_batch(batch_id)
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    if batch.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    if batch.status != BatchStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch is not pending approval (status: {batch.status.value})",
        )

    # Calculate amounts by type
    release_amount = sum(
        r.transaction_amount for r in batch.records if r.decision_type == CommitDecisionType.RELEASE
    )
    hold_amount = sum(
        r.transaction_amount
        for r in batch.records
        if r.decision_type in (CommitDecisionType.HOLD, CommitDecisionType.EXTEND_HOLD)
    )
    return_amount = sum(
        r.transaction_amount for r in batch.records if r.decision_type == CommitDecisionType.RETURN
    )
    reject_amount = sum(
        r.transaction_amount for r in batch.records if r.decision_type == CommitDecisionType.REJECT
    )

    # Build warnings
    warnings = []
    if batch.has_high_risk_items:
        warnings.append(f"Batch contains {batch.high_risk_count} high-risk item(s)")
    if batch.total_amount > Decimal("100000"):
        warnings.append(f"Large batch total: ${batch.total_amount:,.2f}")
    if batch.created_by_user_id == current_user.id:
        warnings.append("You created this batch - a different user must approve (dual control)")

    return BatchConfirmationDialog(
        batch_id=batch.id,
        batch_number=batch.batch_number,
        total_records=batch.total_records,
        total_amount=batch.total_amount,
        release_count=batch.release_count,
        release_amount=release_amount,
        hold_count=batch.hold_count,
        hold_amount=hold_amount,
        return_count=batch.return_count,
        return_amount=return_amount,
        reject_count=batch.reject_count,
        reject_amount=reject_amount,
        escalate_count=batch.escalate_count,
        has_high_risk_items=batch.has_high_risk_items,
        high_risk_count=batch.high_risk_count,
        requires_dual_control=True,
        warnings=warnings,
    )


@router.post("/batches/{batch_id}/approve", response_model=BatchResponse)
async def approve_batch(
    request: Request,
    batch_id: str,
    approval: BatchApprovalRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "approve"))],
):
    """
    Approve a batch for file generation.

    Enforces dual control - approver must be different from creator.
    """
    connector = ConnectorService(db)

    try:
        batch = await connector.approve_batch(
            batch_id=batch_id,
            approver_user_id=current_user.id,
            approval_notes=approval.approval_notes,
        )
    except DualControlViolation as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    except BatchStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.DECISION_APPROVED,
        resource_type="commit_batch",
        resource_id=batch.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Approved commit batch: {batch.batch_number}",
        metadata={"notes": approval.approval_notes},
    )

    return _batch_to_response(batch)


@router.post("/batches/{batch_id}/cancel", response_model=BatchResponse)
async def cancel_batch(
    request: Request,
    batch_id: str,
    cancel_data: BatchCancelRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "create"))],
):
    """Cancel a batch before file generation."""
    connector = ConnectorService(db)

    try:
        batch = await connector.cancel_batch(
            batch_id=batch_id,
            user_id=current_user.id,
            reason=cancel_data.reason,
        )
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    except BatchStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.DELETE,
        resource_type="commit_batch",
        resource_id=batch.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Cancelled commit batch: {batch.batch_number}",
        metadata={"reason": cancel_data.reason},
    )

    return _batch_to_response(batch)


# =============================================================================
# FILE GENERATION ENDPOINTS
# =============================================================================


@router.post("/batches/{batch_id}/generate", response_model=BatchFileResponse)
async def generate_batch_file(
    request: Request,
    batch_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "approve"))],
):
    """
    Generate commit file for an approved batch.

    The file is stored and can be downloaded separately.
    """
    connector = ConnectorService(db)

    try:
        file_name, content, checksum = await connector.generate_file(batch_id)
        batch = await connector.get_batch(batch_id)
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    except BatchStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except FileGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.EXPORT,
        resource_type="commit_batch",
        resource_id=batch.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Generated commit file: {file_name}",
        metadata={
            "file_name": file_name,
            "checksum": checksum,
            "size_bytes": len(content),
        },
    )

    return BatchFileResponse(
        batch_id=batch.id,
        batch_number=batch.batch_number,
        file_name=file_name,
        file_checksum=checksum,
        file_size_bytes=len(content),
        record_count=batch.file_record_count or 0,
        generated_at=batch.file_generated_at or datetime.now(timezone.utc),
    )


@router.get("/batches/{batch_id}/download")
async def download_batch_file(
    batch_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
):
    """Download the generated commit file."""
    connector = ConnectorService(db)

    try:
        batch = await connector.get_batch(batch_id)
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    if batch.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    if batch.status not in (
        BatchStatus.GENERATED,
        BatchStatus.TRANSMITTED,
        BatchStatus.ACKNOWLEDGED,
        BatchStatus.COMPLETED,
        BatchStatus.PARTIALLY_PROCESSED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File not yet generated",
        )

    # Regenerate file (deterministic - will produce same content)
    try:
        file_name, content, checksum = await connector.generate_file(batch_id)
    except Exception:
        # If regeneration fails, the batch may have been modified
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate file",
        )

    # Verify checksum matches original
    if batch.file_checksum and checksum != batch.file_checksum:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Checksum mismatch - file integrity error",
        )

    # Return file as download
    return StreamingResponse(
        iter([content]),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "X-Checksum-SHA256": checksum,
        },
    )


@router.post("/batches/{batch_id}/mark-transmitted", response_model=BatchResponse)
async def mark_batch_transmitted(
    request: Request,
    batch_id: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "approve"))],
    transmission_id: str | None = None,
):
    """Mark batch as transmitted to bank middleware."""
    connector = ConnectorService(db)

    try:
        batch = await connector.mark_transmitted(
            batch_id=batch_id,
            transmission_id=transmission_id,
        )
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    except BatchStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.UPDATE,
        resource_type="commit_batch",
        resource_id=batch.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Marked batch as transmitted: {batch.batch_number}",
        metadata={"transmission_id": transmission_id},
    )

    return _batch_to_response(batch)


# =============================================================================
# ACKNOWLEDGEMENT ENDPOINTS
# =============================================================================


@router.post("/batches/{batch_id}/acknowledgement", response_model=AcknowledgementResponse)
async def process_acknowledgement(
    request: Request,
    batch_id: str,
    ack_data: AcknowledgementRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "approve"))],
):
    """Process acknowledgement from bank middleware."""
    connector = ConnectorService(db)

    try:
        ack = await connector.process_acknowledgement(
            batch_id=batch_id,
            ack_data=ack_data.model_dump(),
            user_id=current_user.id,
        )
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )
    except BatchStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.UPDATE,
        resource_type="commit_batch",
        resource_id=batch_id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Processed acknowledgement: {ack.status.value}",
        metadata={
            "accepted": ack.accepted_count,
            "rejected": ack.rejected_count,
            "pending": ack.pending_count,
        },
    )

    return AcknowledgementResponse(
        id=ack.id,
        batch_id=ack.batch_id,
        ack_file_name=ack.ack_file_name,
        ack_file_received_at=ack.ack_file_received_at,
        status=ack.status,
        bank_reference_id=ack.bank_reference_id,
        bank_batch_id=ack.bank_batch_id,
        total_records=ack.total_records,
        accepted_count=ack.accepted_count,
        rejected_count=ack.rejected_count,
        pending_count=ack.pending_count,
        processed_at=ack.processed_at,
        processed_by_user_id=ack.processed_by_user_id,
        created_at=ack.created_at,
        updated_at=ack.updated_at,
    )


# =============================================================================
# RECONCILIATION ENDPOINTS
# =============================================================================


@router.post("/reconciliation", response_model=ReconciliationReportResponse)
async def generate_reconciliation_report(
    request: Request,
    report_request: ReconciliationReportRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
):
    """Generate daily reconciliation report."""
    connector = ConnectorService(db)

    report = await connector.generate_reconciliation_report(
        tenant_id=current_user.tenant_id,
        report_date=report_request.report_date,
        user_id=current_user.id,
    )

    return _reconciliation_to_response(report)


@router.get("/reconciliation/{report_date}", response_model=ReconciliationReportResponse)
async def get_reconciliation_report(
    report_date: str,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
):
    """Get reconciliation report for a specific date."""
    try:
        date = datetime.fromisoformat(report_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        )

    result = await db.execute(
        select(ReconciliationReport).where(
            ReconciliationReport.tenant_id == current_user.tenant_id,
            func.date(ReconciliationReport.report_date) == date.date(),
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found for this date",
        )

    return _reconciliation_to_response(report)


# =============================================================================
# FAILED RECORD MANAGEMENT
# =============================================================================


@router.get("/records/failed", response_model=list[RecordSummary])
async def list_failed_records(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
    limit: int = 100,
):
    """List failed records requiring resolution."""
    connector = ConnectorService(db)
    records = await connector.get_failed_records(
        tenant_id=current_user.tenant_id,
        limit=limit,
    )

    return [_record_to_summary(r) for r in records]


@router.post("/records/{record_id}/resolve", response_model=RecordSummary)
async def resolve_failed_record(
    request: Request,
    record_id: str,
    resolution: RecordResolutionRequest,
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "approve"))],
):
    """Manually resolve a failed record."""
    connector = ConnectorService(db)

    try:
        record = await connector.resolve_record(
            record_id=record_id,
            user_id=current_user.id,
            resolution_notes=resolution.resolution_notes,
        )
    except ConnectorError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.UPDATE,
        resource_type="commit_record",
        resource_id=record.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        description=f"Manually resolved failed record",
        metadata={"notes": resolution.resolution_notes},
    )

    return _record_to_summary(record)


# =============================================================================
# DASHBOARD
# =============================================================================


@router.get("/dashboard", response_model=ConnectorDashboard)
async def get_connector_dashboard(
    db: DBSession,
    current_user: Annotated[object, Depends(require_permission("connector", "view"))],
):
    """Get connector dashboard summary."""
    connector = ConnectorService(db)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Pending work
    pending_batches = await connector.get_pending_batches(current_user.tenant_id)
    awaiting_ack = await connector.get_awaiting_ack_batches(current_user.tenant_id)
    failed_records = await connector.get_failed_records(current_user.tenant_id, limit=1000)

    # Today's activity
    today_batches_result = await db.execute(
        select(CommitBatch).where(
            CommitBatch.tenant_id == current_user.tenant_id,
            CommitBatch.created_at >= today,
        )
    )
    today_batches = today_batches_result.scalars().all()

    transmitted_today = [b for b in today_batches if b.transmitted_at and b.transmitted_at >= today]

    # Calculate amounts
    total_amount = sum(b.total_amount for b in today_batches)
    release_amount = sum(b.total_amount for b in today_batches)  # Simplified
    hold_amount = Decimal("0.00")
    return_amount = Decimal("0.00")

    # Past deadline
    past_deadline = [
        b
        for b in awaiting_ack
        if b.transmitted_at
        and (datetime.now(timezone.utc) - b.transmitted_at).total_seconds() > 24 * 3600
    ]

    return ConnectorDashboard(
        batches_pending_approval=len(pending_batches),
        batches_awaiting_acknowledgement=len(awaiting_ack),
        records_failed_unresolved=len(failed_records),
        batches_created_today=len(today_batches),
        batches_transmitted_today=len(transmitted_today),
        records_processed_today=sum(b.total_records for b in transmitted_today),
        records_accepted_today=sum(b.records_accepted or 0 for b in today_batches),
        records_rejected_today=sum(b.records_rejected or 0 for b in today_batches),
        total_amount_today=total_amount,
        release_amount_today=release_amount,
        hold_amount_today=hold_amount,
        return_amount_today=return_amount,
        batches_past_ack_deadline=len(past_deadline),
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _batch_to_response(batch: CommitBatch, include_records: bool = False) -> BatchResponse:
    """Convert batch model to response schema."""
    records = None
    if include_records and hasattr(batch, "records") and batch.records:
        records = [_record_to_summary(r) for r in batch.records]

    return BatchResponse(
        id=batch.id,
        tenant_id=batch.tenant_id,
        batch_number=batch.batch_number,
        bank_config_id=batch.bank_config_id,
        description=batch.description,
        status=batch.status,
        total_records=batch.total_records,
        total_amount=batch.total_amount,
        release_count=batch.release_count,
        hold_count=batch.hold_count,
        return_count=batch.return_count,
        reject_count=batch.reject_count,
        escalate_count=batch.escalate_count,
        has_high_risk_items=batch.has_high_risk_items,
        high_risk_count=batch.high_risk_count,
        created_by_user_id=batch.created_by_user_id,
        reviewer_user_id=batch.reviewer_user_id,
        reviewed_at=batch.reviewed_at,
        approver_user_id=batch.approver_user_id,
        approved_at=batch.approved_at,
        approval_notes=batch.approval_notes,
        file_generated_at=batch.file_generated_at,
        file_name=batch.file_name,
        file_checksum=batch.file_checksum,
        file_size_bytes=batch.file_size_bytes,
        file_record_count=batch.file_record_count,
        batch_hash=batch.batch_hash,
        transmitted_at=batch.transmitted_at,
        transmission_id=batch.transmission_id,
        transmission_error=batch.transmission_error,
        acknowledged_at=batch.acknowledged_at,
        ack_status=batch.ack_status,
        ack_reference=batch.ack_reference,
        records_accepted=batch.records_accepted,
        records_rejected=batch.records_rejected,
        records_pending=batch.records_pending,
        cancelled_at=batch.cancelled_at,
        cancelled_by_user_id=batch.cancelled_by_user_id,
        cancellation_reason=batch.cancellation_reason,
        records=records,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _record_to_summary(record: CommitRecord) -> RecordSummary:
    """Convert record model to summary schema."""
    return RecordSummary(
        id=record.id,
        sequence_number=record.sequence_number,
        decision_id=record.decision_id,
        check_item_id=record.check_item_id,
        item_id=record.item_id,
        decision_hash=record.decision_hash,
        status=record.status,
        decision_type=record.decision_type,
        account_number_masked=record.account_number_masked,
        transaction_amount=record.transaction_amount,
        reviewer_user_id=record.reviewer_user_id,
        approver_user_id=record.approver_user_id,
        decision_timestamp=record.decision_timestamp,
        hold_amount=record.hold_amount,
        hold_expiration_date=record.hold_expiration_date,
        hold_reason_code=record.hold_reason_code,
        error_category=record.error_category,
        error_code=record.error_code,
        error_message=record.error_message,
        manually_resolved_at=record.manually_resolved_at,
        resolution_notes=record.resolution_notes,
    )


def _reconciliation_to_response(report: ReconciliationReport) -> ReconciliationReportResponse:
    """Convert reconciliation report model to response schema."""
    return ReconciliationReportResponse(
        id=report.id,
        tenant_id=report.tenant_id,
        report_date=report.report_date,
        period_start=report.period_start,
        period_end=report.period_end,
        decisions_approved=report.decisions_approved,
        decisions_amount_total=report.decisions_amount_total,
        files_generated=report.files_generated,
        files_transmitted=report.files_transmitted,
        records_included=report.records_included,
        records_accepted=report.records_accepted,
        records_rejected=report.records_rejected,
        records_pending=report.records_pending,
        exceptions_new=report.exceptions_new,
        exceptions_resolved=report.exceptions_resolved,
        exceptions_outstanding=report.exceptions_outstanding,
        release_amount=report.release_amount,
        hold_amount=report.hold_amount,
        return_amount=report.return_amount,
        reject_amount=report.reject_amount,
        batch_ids=report.batch_ids,
        generated_at=report.generated_at,
        generated_by_user_id=report.generated_by_user_id,
        approved_at=report.approved_at,
        approved_by_user_id=report.approved_by_user_id,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )
