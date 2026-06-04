"""Item Context Connector API Endpoints.

Manages SFTP connectors for importing item context data:
- CRUD operations for connectors
- Connection testing
- Manual import triggering
- Import history and error tracking

Required permissions:
- item_context_connector:view - View connectors and history
- item_context_connector:manage - Create/update/delete connectors
- item_context_connector:import - Trigger imports
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.audit.service import AuditService
from app.core.encryption import encrypt_value
from app.models.audit import AuditAction
from app.models.item_context_connector import (
    FIELD_MAPPING_TEMPLATES,
    ContextConnectorStatus,
    FileFormat,
    ImportStatus,
    ItemContextConnector,
    ItemContextImport,
    ItemContextImportRecord,
    RecordStatus,
)
from app.services.item_context_service import ItemContextImportService
from app.services.sftp_service import SFTPService

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================


class ConnectorCreateRequest(BaseModel):
    """Request to create a new connector."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    source_system: str = Field(..., min_length=1, max_length=50)

    # SFTP Settings
    sftp_host: str = Field(..., min_length=1, max_length=255)
    sftp_port: int = Field(default=22, ge=1, le=65535)
    sftp_username: str = Field(..., min_length=1, max_length=100)
    sftp_password: str | None = Field(default=None, description="Password (will be encrypted)")
    sftp_private_key: str | None = Field(
        default=None, description="SSH private key (will be encrypted)"
    )
    sftp_key_passphrase: str | None = Field(
        default=None, description="Key passphrase (will be encrypted)"
    )

    # SFTP Paths
    sftp_remote_path: str = Field(default="/outbound", max_length=500)
    sftp_archive_path: str | None = Field(default=None, max_length=500)
    sftp_error_path: str | None = Field(default=None, max_length=500)

    # File Settings
    file_pattern: str = Field(default="*.csv", max_length=255)
    file_format: FileFormat = FileFormat.CSV
    file_encoding: str = Field(default="UTF-8", max_length=20)
    file_delimiter: str | None = None
    has_header_row: bool = True
    skip_rows: int = Field(default=0, ge=0)

    # Field Mapping
    field_mapping: dict[str, Any] = Field(default_factory=dict)
    fixed_width_config: dict[str, Any] | None = None

    # Matching
    match_by_external_item_id: bool = False
    match_field: str = Field(default="account_id", max_length=50)

    # Schedule
    schedule_enabled: bool = False
    schedule_cron: str | None = Field(default=None, max_length=100)
    schedule_timezone: str = Field(default="America/New_York", max_length=50)

    # Processing
    max_records_per_file: int = Field(default=100000, ge=1)
    batch_size: int = Field(default=1000, ge=1, le=10000)
    fail_on_validation_error: bool = False
    update_existing: bool = True


class ConnectorUpdateRequest(BaseModel):
    """Request to update a connector."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_enabled: bool | None = None

    # SFTP Settings (partial update)
    sftp_host: str | None = Field(default=None, min_length=1, max_length=255)
    sftp_port: int | None = Field(default=None, ge=1, le=65535)
    sftp_username: str | None = Field(default=None, min_length=1, max_length=100)
    sftp_password: str | None = Field(default=None, description="New password (will be encrypted)")
    sftp_private_key: str | None = Field(
        default=None, description="New SSH key (will be encrypted)"
    )
    sftp_key_passphrase: str | None = Field(
        default=None, description="New passphrase (will be encrypted)"
    )

    # SFTP Paths
    sftp_remote_path: str | None = Field(default=None, max_length=500)
    sftp_archive_path: str | None = None
    sftp_error_path: str | None = None

    # File Settings
    file_pattern: str | None = Field(default=None, max_length=255)
    file_format: FileFormat | None = None
    file_encoding: str | None = Field(default=None, max_length=20)
    file_delimiter: str | None = None
    has_header_row: bool | None = None
    skip_rows: int | None = Field(default=None, ge=0)

    # Field Mapping
    field_mapping: dict[str, Any] | None = None
    fixed_width_config: dict[str, Any] | None = None

    # Matching
    match_by_external_item_id: bool | None = None
    match_field: str | None = Field(default=None, max_length=50)

    # Schedule
    schedule_enabled: bool | None = None
    schedule_cron: str | None = Field(default=None, max_length=100)
    schedule_timezone: str | None = Field(default=None, max_length=50)

    # Processing
    max_records_per_file: int | None = Field(default=None, ge=1)
    batch_size: int | None = Field(default=None, ge=1, le=10000)
    fail_on_validation_error: bool | None = None
    update_existing: bool | None = None


class ConnectorResponse(BaseModel):
    """Connector details response."""

    id: str
    tenant_id: str
    name: str
    description: str | None
    source_system: str
    status: ContextConnectorStatus
    is_enabled: bool

    # SFTP (credentials masked)
    sftp_host: str
    sftp_port: int
    sftp_username: str
    sftp_has_password: bool
    sftp_has_key: bool
    sftp_remote_path: str
    sftp_archive_path: str | None
    sftp_error_path: str | None

    # File Settings
    file_pattern: str
    file_format: FileFormat
    file_encoding: str
    file_delimiter: str | None
    has_header_row: bool
    skip_rows: int

    # Field Mapping
    field_mapping: dict[str, Any]
    fixed_width_config: dict[str, Any] | None

    # Matching
    match_by_external_item_id: bool
    match_field: str

    # Schedule
    schedule_enabled: bool
    schedule_cron: str | None
    schedule_timezone: str

    # Processing
    max_records_per_file: int
    batch_size: int
    fail_on_validation_error: bool
    update_existing: bool

    # Status
    last_connection_test_at: datetime | None
    last_connection_test_success: bool | None
    last_import_at: datetime | None
    last_import_file: str | None
    last_import_records: int | None
    consecutive_failures: int
    last_error_at: datetime | None
    last_error_message: str | None

    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class ConnectorListResponse(BaseModel):
    """List of connectors."""

    items: list[ConnectorResponse]
    total: int


class ConnectionTestResponse(BaseModel):
    """Connection test result."""

    success: bool
    message: str
    latency_ms: int | None
    server_version: str | None


class ImportTriggerResponse(BaseModel):
    """Import trigger result."""

    import_id: str
    status: ImportStatus
    message: str


class ImportResponse(BaseModel):
    """Import details response."""

    id: str
    connector_id: str
    file_name: str
    file_path: str
    file_size_bytes: int | None
    file_checksum: str | None
    status: ImportStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None

    total_records: int
    matched_records: int
    applied_records: int
    not_found_records: int
    duplicate_records: int
    invalid_records: int
    error_records: int

    triggered_by: str
    error_message: str | None

    created_at: datetime

    model_config = {"from_attributes": True}


class ImportListResponse(BaseModel):
    """List of imports."""

    items: list[ImportResponse]
    total: int


class ImportRecordResponse(BaseModel):
    """Import error record."""

    id: str
    row_number: int
    status: RecordStatus
    account_id_from_file: str | None
    external_item_id_from_file: str | None
    check_item_id: str | None
    context_data: dict[str, Any] | None
    error_message: str | None

    model_config = {"from_attributes": True}


class FieldMappingTemplateResponse(BaseModel):
    """Field mapping template."""

    name: str
    description: str
    mapping: dict[str, Any]


# =============================================================================
# CONNECTOR CRUD ENDPOINTS
# =============================================================================


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    db: DBSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
):
    """List all item context connectors for the tenant."""
    # Get tenant from user (simplified - in production would come from auth context)
    tenant_id = current_user.tenant_id

    # Count total
    count_query = select(func.count(ItemContextConnector.id)).where(
        ItemContextConnector.tenant_id == tenant_id
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Get connectors
    query = (
        select(ItemContextConnector)
        .where(ItemContextConnector.tenant_id == tenant_id)
        .order_by(ItemContextConnector.name)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    connectors = result.scalars().all()

    return ConnectorListResponse(items=[_connector_to_response(c) for c in connectors], total=total)


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    request: ConnectorCreateRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new item context connector."""
    tenant_id = current_user.tenant_id

    # Check for duplicate name
    existing = await db.execute(
        select(ItemContextConnector).where(
            ItemContextConnector.tenant_id == tenant_id, ItemContextConnector.name == request.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector with name '{request.name}' already exists",
        )

    # Create connector
    connector = ItemContextConnector(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        source_system=request.source_system,
        status=ContextConnectorStatus.INACTIVE,
        is_enabled=False,
        # SFTP
        sftp_host=request.sftp_host,
        sftp_port=request.sftp_port,
        sftp_username=request.sftp_username,
        sftp_password_encrypted=(
            encrypt_value(request.sftp_password) if request.sftp_password else None
        ),
        sftp_private_key_encrypted=(
            encrypt_value(request.sftp_private_key) if request.sftp_private_key else None
        ),
        sftp_key_passphrase_encrypted=(
            encrypt_value(request.sftp_key_passphrase) if request.sftp_key_passphrase else None
        ),
        # Paths
        sftp_remote_path=request.sftp_remote_path,
        sftp_archive_path=request.sftp_archive_path,
        sftp_error_path=request.sftp_error_path,
        # File
        file_pattern=request.file_pattern,
        file_format=request.file_format,
        file_encoding=request.file_encoding,
        file_delimiter=request.file_delimiter,
        has_header_row=request.has_header_row,
        skip_rows=request.skip_rows,
        # Mapping
        field_mapping=request.field_mapping,
        fixed_width_config=request.fixed_width_config,
        # Matching
        match_by_external_item_id=request.match_by_external_item_id,
        match_field=request.match_field,
        # Schedule
        schedule_enabled=request.schedule_enabled,
        schedule_cron=request.schedule_cron,
        schedule_timezone=request.schedule_timezone,
        # Processing
        max_records_per_file=request.max_records_per_file,
        batch_size=request.batch_size,
        fail_on_validation_error=request.fail_on_validation_error,
        update_existing=request.update_existing,
        created_by_user_id=current_user.id,
    )

    db.add(connector)

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.CREATE,
        resource_type="item_context_connector",
        resource_id=connector.id,
        user_id=current_user.id,
        username=current_user.username,
        description=f"Created item context connector: {connector.name}",
    )

    await db.commit()
    await db.refresh(connector)

    return _connector_to_response(connector)


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get a specific connector by ID."""
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)
    return _connector_to_response(connector)


@router.patch("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    connector_id: str,
    request: ConnectorUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update a connector."""
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)

    # Update fields
    update_data = request.model_dump(exclude_unset=True)

    # Handle encrypted fields
    if "sftp_password" in update_data:
        if update_data["sftp_password"]:
            connector.sftp_password_encrypted = encrypt_value(update_data["sftp_password"])
        del update_data["sftp_password"]

    if "sftp_private_key" in update_data:
        if update_data["sftp_private_key"]:
            connector.sftp_private_key_encrypted = encrypt_value(update_data["sftp_private_key"])
        del update_data["sftp_private_key"]

    if "sftp_key_passphrase" in update_data:
        if update_data["sftp_key_passphrase"]:
            connector.sftp_key_passphrase_encrypted = encrypt_value(
                update_data["sftp_key_passphrase"]
            )
        del update_data["sftp_key_passphrase"]

    # Apply remaining updates
    for field, value in update_data.items():
        if hasattr(connector, field):
            setattr(connector, field, value)

    connector.last_modified_by_user_id = current_user.id

    # Audit log
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.UPDATE,
        resource_type="item_context_connector",
        resource_id=connector.id,
        user_id=current_user.id,
        username=current_user.username,
        description=f"Updated item context connector: {connector.name}",
    )

    await db.commit()
    await db.refresh(connector)

    return _connector_to_response(connector)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete a connector."""
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)

    # Audit log before deletion
    audit_service = AuditService(db)
    await audit_service.log(
        action=AuditAction.DELETE,
        resource_type="item_context_connector",
        resource_id=connector.id,
        user_id=current_user.id,
        username=current_user.username,
        description=f"Deleted item context connector: {connector.name}",
    )

    await db.delete(connector)
    await db.commit()


# =============================================================================
# CONNECTION & IMPORT ENDPOINTS
# =============================================================================


@router.post("/{connector_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connector_id: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Test SFTP connection for a connector."""
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)

    sftp = SFTPService(connector)
    result = await sftp.test_connection()

    # Update connector with test results
    connector.last_connection_test_at = datetime.now(timezone.utc)
    connector.last_connection_test_success = result.success
    connector.last_connection_test_error = result.error_details

    await db.commit()

    return ConnectionTestResponse(
        success=result.success,
        message=result.message,
        latency_ms=result.latency_ms,
        server_version=result.server_version,
    )


@router.post("/{connector_id}/import", response_model=ImportTriggerResponse)
async def trigger_import(
    connector_id: str,
    db: DBSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    file_limit: int | None = None,
):
    """
    Trigger an import for a connector.

    The import runs in the background. Check import history for status.
    """
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)

    if not connector.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connector is disabled. Enable it before triggering imports.",
        )

    # Create a pending import record
    import_record = ItemContextImport(
        id=str(uuid.uuid4()),
        connector_id=connector.id,
        tenant_id=connector.tenant_id,
        file_name="PENDING",
        file_path="",
        status=ImportStatus.PENDING,
        triggered_by="api",
        triggered_by_user_id=current_user.id,
    )
    db.add(import_record)
    await db.commit()

    # Run import in background
    # Note: In production, use Celery or similar for proper background task handling
    background_tasks.add_task(
        _run_import_background,
        connector.id,
        current_user.id,
        file_limit,
    )

    return ImportTriggerResponse(
        import_id=import_record.id,
        status=ImportStatus.PENDING,
        message="Import started. Check import history for progress.",
    )


@router.get("/{connector_id}/imports", response_model=ImportListResponse)
async def list_imports(
    connector_id: str,
    db: DBSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
):
    """Get import history for a connector."""
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)

    # Count
    count_query = select(func.count(ItemContextImport.id)).where(
        ItemContextImport.connector_id == connector.id
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Get imports
    query = (
        select(ItemContextImport)
        .where(ItemContextImport.connector_id == connector.id)
        .order_by(ItemContextImport.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    imports = result.scalars().all()

    return ImportListResponse(
        items=[ImportResponse.model_validate(i) for i in imports], total=total
    )


@router.get("/{connector_id}/imports/{import_id}", response_model=ImportResponse)
async def get_import(
    connector_id: str,
    import_id: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get details of a specific import."""
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)

    result = await db.execute(
        select(ItemContextImport).where(
            ItemContextImport.id == import_id, ItemContextImport.connector_id == connector.id
        )
    )
    import_record = result.scalar_one_or_none()

    if not import_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    return ImportResponse.model_validate(import_record)


@router.get("/{connector_id}/imports/{import_id}/errors")
async def get_import_errors(
    connector_id: str,
    import_id: str,
    db: DBSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> list[ImportRecordResponse]:
    """Get error records for an import."""
    connector = await _get_connector_or_404(db, connector_id, current_user.tenant_id)

    # Verify import belongs to connector
    import_check = await db.execute(
        select(ItemContextImport.id).where(
            ItemContextImport.id == import_id, ItemContextImport.connector_id == connector.id
        )
    )
    if not import_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    # Get error records
    query = (
        select(ItemContextImportRecord)
        .where(
            ItemContextImportRecord.import_id == import_id,
            ItemContextImportRecord.status.in_(
                [
                    RecordStatus.NOT_FOUND,
                    RecordStatus.INVALID,
                    RecordStatus.ERROR,
                    RecordStatus.DUPLICATE,
                ]
            ),
        )
        .order_by(ItemContextImportRecord.row_number)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    records = result.scalars().all()

    return [ImportRecordResponse.model_validate(r) for r in records]


# =============================================================================
# TEMPLATE ENDPOINTS
# =============================================================================


@router.get("/templates/field-mappings")
async def list_field_mapping_templates() -> list[FieldMappingTemplateResponse]:
    """Get available field mapping templates for common core systems."""
    templates = []

    descriptions = {
        "fiserv_premier": "Fiserv Premier/DNA - Standard context export format",
        "jack_henry_silverlake": "Jack Henry Silverlake - Account context export",
        "q2_core": "Q2 Core - Transaction context format",
    }

    for name, mapping in FIELD_MAPPING_TEMPLATES.items():
        templates.append(
            FieldMappingTemplateResponse(
                name=name,
                description=descriptions.get(name, f"Template for {name}"),
                mapping=mapping,
            )
        )

    return templates


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def _get_connector_or_404(
    db: DBSession, connector_id: str, tenant_id: str
) -> ItemContextConnector:
    """Get connector by ID or raise 404."""
    result = await db.execute(
        select(ItemContextConnector).where(
            ItemContextConnector.id == connector_id, ItemContextConnector.tenant_id == tenant_id
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    return connector


def _connector_to_response(connector: ItemContextConnector) -> ConnectorResponse:
    """Convert connector model to response."""
    return ConnectorResponse(
        id=connector.id,
        tenant_id=connector.tenant_id,
        name=connector.name,
        description=connector.description,
        source_system=connector.source_system,
        status=connector.status,
        is_enabled=connector.is_enabled,
        sftp_host=connector.sftp_host,
        sftp_port=connector.sftp_port,
        sftp_username=connector.sftp_username,
        sftp_has_password=bool(connector.sftp_password_encrypted),
        sftp_has_key=bool(connector.sftp_private_key_encrypted),
        sftp_remote_path=connector.sftp_remote_path,
        sftp_archive_path=connector.sftp_archive_path,
        sftp_error_path=connector.sftp_error_path,
        file_pattern=connector.file_pattern,
        file_format=connector.file_format,
        file_encoding=connector.file_encoding,
        file_delimiter=connector.file_delimiter,
        has_header_row=connector.has_header_row,
        skip_rows=connector.skip_rows,
        field_mapping=connector.field_mapping,
        fixed_width_config=connector.fixed_width_config,
        match_by_external_item_id=connector.match_by_external_item_id,
        match_field=connector.match_field,
        schedule_enabled=connector.schedule_enabled,
        schedule_cron=connector.schedule_cron,
        schedule_timezone=connector.schedule_timezone,
        max_records_per_file=connector.max_records_per_file,
        batch_size=connector.batch_size,
        fail_on_validation_error=connector.fail_on_validation_error,
        update_existing=connector.update_existing,
        last_connection_test_at=connector.last_connection_test_at,
        last_connection_test_success=connector.last_connection_test_success,
        last_import_at=connector.last_import_at,
        last_import_file=connector.last_import_file,
        last_import_records=connector.last_import_records,
        consecutive_failures=connector.consecutive_failures,
        last_error_at=connector.last_error_at,
        last_error_message=connector.last_error_message,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


async def _run_import_background(
    connector_id: str,
    user_id: str,
    file_limit: int | None,
):
    """
    Run import in background.

    Note: In production, this should use Celery or similar
    for proper task management, retries, and monitoring.
    """
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        # Get connector
        result = await db.execute(
            select(ItemContextConnector).where(ItemContextConnector.id == connector_id)
        )
        connector = result.scalar_one_or_none()

        if not connector:
            return

        # Run import
        service = ItemContextImportService(db)
        await service.run_import(
            connector=connector,
            triggered_by="api",
            triggered_by_user_id=user_id,
            file_limit=file_limit,
        )
