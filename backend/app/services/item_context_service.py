"""Item Context Import Service.

Handles the end-to-end process of importing item context data:
1. Connect to SFTP server
2. Download matching files
3. Parse flat files (CSV, TSV, fixed-width, pipe-delimited)
4. Match records to existing CheckItems
5. Enrich CheckItems with context data
6. Archive/delete processed files
7. Track import progress and errors

Context fields enriched on CheckItem:
- account_tenure_days
- current_balance, average_balance_30d
- avg_check_amount_30d/90d/365d
- check_std_dev_30d, max_check_amount_90d
- check_frequency_30d
- returned_item_count_90d, exception_count_90d
- relationship_id
"""

import csv
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Generator

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.check import CheckItem
from app.models.item_context_connector import (
    ItemContextConnector,
    ItemContextImport,
    ItemContextImportRecord,
    ContextConnectorStatus,
    FileFormat,
    ImportStatus,
    RecordStatus,
)
from app.services.sftp_service import SFTPService, SFTPFile


# Context fields that can be imported (maps to CheckItem columns)
CONTEXT_FIELDS = {
    "account_tenure_days": {"type": "int", "column": "account_tenure_days"},
    "current_balance": {"type": "decimal", "column": "current_balance"},
    "average_balance_30d": {"type": "decimal", "column": "average_balance_30d"},
    "avg_check_amount_30d": {"type": "decimal", "column": "avg_check_amount_30d"},
    "avg_check_amount_90d": {"type": "decimal", "column": "avg_check_amount_90d"},
    "avg_check_amount_365d": {"type": "decimal", "column": "avg_check_amount_365d"},
    "check_std_dev_30d": {"type": "decimal", "column": "check_std_dev_30d"},
    "max_check_amount_90d": {"type": "decimal", "column": "max_check_amount_90d"},
    "check_frequency_30d": {"type": "int", "column": "check_frequency_30d"},
    "returned_item_count_90d": {"type": "int", "column": "returned_item_count_90d"},
    "exception_count_90d": {"type": "int", "column": "exception_count_90d"},
    "relationship_id": {"type": "str", "column": "relationship_id"},
}


class FileParser:
    """
    Parses flat files in various formats.

    Supports: CSV, TSV, pipe-delimited, fixed-width
    """

    def __init__(
        self,
        file_format: FileFormat,
        field_mapping: dict[str, Any],
        encoding: str = "UTF-8",
        delimiter: str | None = None,
        has_header: bool = True,
        skip_rows: int = 0,
        fixed_width_config: dict[str, Any] | None = None,
    ):
        self.file_format = file_format
        self.field_mapping = field_mapping
        self.encoding = encoding
        self.delimiter = delimiter
        self.has_header = has_header
        self.skip_rows = skip_rows
        self.fixed_width_config = fixed_width_config or {}

    def _get_delimiter(self) -> str:
        """Get the appropriate delimiter for the file format."""
        if self.delimiter:
            return self.delimiter

        delimiters = {
            FileFormat.CSV: ",",
            FileFormat.TSV: "\t",
            FileFormat.PIPE_DELIMITED: "|",
        }
        return delimiters.get(self.file_format, ",")

    def parse_file(self, file_path: str) -> Generator[tuple[int, dict[str, Any]], None, None]:
        """
        Parse file and yield (row_number, parsed_data) tuples.

        Args:
            file_path: Path to the file to parse

        Yields:
            Tuple of (row_number, dict of field_name -> value)
        """
        if self.file_format == FileFormat.FIXED_WIDTH:
            yield from self._parse_fixed_width(file_path)
        else:
            yield from self._parse_delimited(file_path)

    def _parse_delimited(self, file_path: str) -> Generator[tuple[int, dict[str, Any]], None, None]:
        """Parse delimited file (CSV, TSV, pipe)."""
        delimiter = self._get_delimiter()

        with open(file_path, "r", encoding=self.encoding, newline="") as f:
            reader = csv.reader(f, delimiter=delimiter)

            row_num = 0
            header_row = None

            for row in reader:
                row_num += 1

                # Skip header
                if row_num == 1 and self.has_header:
                    header_row = row
                    continue

                # Skip configured rows
                if row_num <= self.skip_rows + (1 if self.has_header else 0):
                    continue

                # Parse row using field mapping
                parsed = self._map_row_to_fields(row, header_row)
                yield (row_num, parsed)

    def _parse_fixed_width(self, file_path: str) -> Generator[tuple[int, dict[str, Any]], None, None]:
        """Parse fixed-width file."""
        with open(file_path, "r", encoding=self.encoding) as f:
            row_num = 0

            for line in f:
                row_num += 1

                # Skip header
                if row_num == 1 and self.has_header:
                    continue

                # Skip configured rows
                if row_num <= self.skip_rows + (1 if self.has_header else 0):
                    continue

                # Parse row using fixed-width positions
                parsed = self._map_fixed_width_to_fields(line)
                yield (row_num, parsed)

    def _map_row_to_fields(
        self,
        row: list[str],
        header_row: list[str] | None
    ) -> dict[str, Any]:
        """Map a delimited row to field names using the field mapping."""
        result = {}

        for field_name, mapping in self.field_mapping.items():
            value = None

            # Get value by column index or header name
            if "column" in mapping and isinstance(mapping["column"], int):
                if mapping["column"] < len(row):
                    value = row[mapping["column"]].strip()
            elif "name" in mapping and header_row:
                try:
                    col_idx = header_row.index(mapping["name"])
                    if col_idx < len(row):
                        value = row[col_idx].strip()
                except ValueError:
                    pass

            # Convert type
            if value:
                value = self._convert_value(value, mapping.get("type", "str"))

            result[field_name] = value

        return result

    def _map_fixed_width_to_fields(self, line: str) -> dict[str, Any]:
        """Map a fixed-width line to field names."""
        result = {}

        config = self.fixed_width_config or self.field_mapping

        for field_name, mapping in config.items():
            value = None

            if "start" in mapping and "end" in mapping:
                start = mapping["start"]
                end = mapping["end"]
                if len(line) >= end:
                    value = line[start:end].strip()
            elif "start" in mapping and "length" in mapping:
                start = mapping["start"]
                length = mapping["length"]
                if len(line) >= start + length:
                    value = line[start:start + length].strip()

            # Convert type
            if value:
                value = self._convert_value(value, mapping.get("type", "str"))

            result[field_name] = value

        return result

    def _convert_value(self, value: str, value_type: str) -> Any:
        """Convert string value to the specified type."""
        if not value:
            return None

        try:
            if value_type == "int":
                # Handle numeric strings with commas
                return int(value.replace(",", ""))
            elif value_type == "decimal":
                # Handle currency formatting
                clean_value = value.replace(",", "").replace("$", "").strip()
                return Decimal(clean_value)
            elif value_type == "bool":
                return value.lower() in ("true", "1", "yes", "y")
            else:
                return value
        except (ValueError, InvalidOperation):
            return None


class ItemContextImportService:
    """
    Service for importing item context data from flat files.

    Orchestrates the full import process:
    1. SFTP connection and file retrieval
    2. File parsing and validation
    3. CheckItem matching and enrichment
    4. Progress tracking and error handling
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_import(
        self,
        connector: ItemContextConnector,
        triggered_by: str = "manual",
        triggered_by_user_id: str | None = None,
        file_limit: int | None = None,
    ) -> list[ItemContextImport]:
        """
        Run a full import cycle for a connector.

        Args:
            connector: The connector configuration to use
            triggered_by: "manual", "scheduled", or "api"
            triggered_by_user_id: User who triggered (if manual/api)
            file_limit: Maximum number of files to process (None = all)

        Returns:
            List of ItemContextImport records for processed files
        """
        imports = []

        # Connect to SFTP
        sftp = SFTPService(connector)
        try:
            connection_result = await sftp.connect()

            if not connection_result.success:
                # Create failed import record
                failed_import = ItemContextImport(
                    id=str(uuid.uuid4()),
                    connector_id=connector.id,
                    tenant_id=connector.tenant_id,
                    file_name="CONNECTION_FAILED",
                    file_path="",
                    status=ImportStatus.FAILED,
                    triggered_by=triggered_by,
                    triggered_by_user_id=triggered_by_user_id,
                    error_message=connection_result.message,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                self.db.add(failed_import)
                await self.db.commit()

                # Update connector error status
                connector.status = ContextConnectorStatus.ERROR
                connector.consecutive_failures += 1
                connector.last_error_at = datetime.now(timezone.utc)
                connector.last_error_message = connection_result.message
                await self.db.commit()

                return [failed_import]

            # List available files
            files = await sftp.list_files()

            if file_limit:
                files = files[:file_limit]

            # Process each file
            for sftp_file in files:
                if sftp_file.is_directory:
                    continue

                import_record = await self._process_file(
                    connector=connector,
                    sftp=sftp,
                    sftp_file=sftp_file,
                    triggered_by=triggered_by,
                    triggered_by_user_id=triggered_by_user_id,
                )
                imports.append(import_record)

            # Update connector success status
            if imports:
                successful = [i for i in imports if i.status == ImportStatus.COMPLETED]
                if successful:
                    connector.status = ContextConnectorStatus.ACTIVE
                    connector.consecutive_failures = 0
                    connector.last_import_at = datetime.now(timezone.utc)
                    connector.last_import_file = successful[-1].file_name
                    connector.last_import_records = sum(i.applied_records for i in successful)
                    await self.db.commit()

        finally:
            await sftp.disconnect()

        return imports

    async def _process_file(
        self,
        connector: ItemContextConnector,
        sftp: SFTPService,
        sftp_file: SFTPFile,
        triggered_by: str,
        triggered_by_user_id: str | None,
    ) -> ItemContextImport:
        """Process a single file from SFTP."""
        started_at = datetime.now(timezone.utc)

        # Create import record
        import_record = ItemContextImport(
            id=str(uuid.uuid4()),
            connector_id=connector.id,
            tenant_id=connector.tenant_id,
            file_name=sftp_file.name,
            file_path=sftp_file.path,
            file_size_bytes=sftp_file.size,
            file_modified_at=sftp_file.modified_at,
            status=ImportStatus.DOWNLOADING,
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
            started_at=started_at,
        )
        self.db.add(import_record)
        await self.db.commit()

        try:
            # Download file
            download_result = await sftp.download_file(sftp_file.path)

            if not download_result.success:
                import_record.status = ImportStatus.FAILED
                import_record.error_message = f"Download failed: {download_result.error}"
                import_record.completed_at = datetime.now(timezone.utc)
                await self.db.commit()
                return import_record

            import_record.file_checksum = download_result.checksum
            import_record.status = ImportStatus.VALIDATING
            await self.db.commit()

            # Parse and process file
            await self._parse_and_apply(
                connector=connector,
                import_record=import_record,
                local_path=download_result.local_path,
            )

            # Determine final status
            if import_record.error_records > 0 or import_record.invalid_records > 0:
                if import_record.applied_records > 0:
                    import_record.status = ImportStatus.PARTIAL
                else:
                    import_record.status = ImportStatus.FAILED
            else:
                import_record.status = ImportStatus.COMPLETED

            import_record.completed_at = datetime.now(timezone.utc)
            import_record.duration_seconds = int(
                (import_record.completed_at - started_at).total_seconds()
            )

            # Archive or delete the remote file
            await self._handle_processed_file(sftp, connector, sftp_file, import_record.status)

            # Clean up local file
            if download_result.local_path and os.path.exists(download_result.local_path):
                os.remove(download_result.local_path)

            await self.db.commit()
            return import_record

        except Exception as e:
            import_record.status = ImportStatus.FAILED
            import_record.error_message = str(e)
            import_record.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            return import_record

    async def _parse_and_apply(
        self,
        connector: ItemContextConnector,
        import_record: ItemContextImport,
        local_path: str,
    ) -> None:
        """Parse file and apply context to CheckItems."""
        import_record.status = ImportStatus.PROCESSING
        await self.db.commit()

        # Create parser
        parser = FileParser(
            file_format=connector.file_format,
            field_mapping=connector.field_mapping,
            encoding=connector.file_encoding,
            delimiter=connector.file_delimiter,
            has_header=connector.has_header_row,
            skip_rows=connector.skip_rows,
            fixed_width_config=connector.fixed_width_config,
        )

        # Track statistics
        stats = {
            "total": 0,
            "matched": 0,
            "applied": 0,
            "not_found": 0,
            "duplicate": 0,
            "invalid": 0,
            "error": 0,
        }
        seen_ids = set()
        batch = []
        batch_size = connector.batch_size

        # Process each row
        for row_num, parsed_data in parser.parse_file(local_path):
            stats["total"] += 1

            if stats["total"] > connector.max_records_per_file:
                break

            # Get matching identifier
            match_id = self._get_match_identifier(connector, parsed_data)

            if not match_id:
                stats["invalid"] += 1
                await self._create_error_record(
                    import_record, row_num, RecordStatus.INVALID,
                    parsed_data, "Missing matching identifier"
                )
                continue

            # Check for duplicates
            if match_id in seen_ids:
                stats["duplicate"] += 1
                await self._create_error_record(
                    import_record, row_num, RecordStatus.DUPLICATE,
                    parsed_data, f"Duplicate {connector.match_field}: {match_id}"
                )
                continue

            seen_ids.add(match_id)

            # Add to batch
            batch.append({
                "row_num": row_num,
                "match_id": match_id,
                "parsed_data": parsed_data,
            })

            # Process batch
            if len(batch) >= batch_size:
                batch_stats = await self._process_batch(connector, import_record, batch)
                for key in batch_stats:
                    stats[key] += batch_stats[key]
                batch = []

        # Process remaining batch
        if batch:
            batch_stats = await self._process_batch(connector, import_record, batch)
            for key in batch_stats:
                stats[key] += batch_stats[key]

        # Update import record with statistics
        import_record.total_records = stats["total"]
        import_record.matched_records = stats["matched"]
        import_record.applied_records = stats["applied"]
        import_record.not_found_records = stats["not_found"]
        import_record.duplicate_records = stats["duplicate"]
        import_record.invalid_records = stats["invalid"]
        import_record.error_records = stats["error"]

    def _get_match_identifier(
        self,
        connector: ItemContextConnector,
        parsed_data: dict[str, Any]
    ) -> str | None:
        """Extract the matching identifier from parsed data."""
        if connector.match_by_external_item_id:
            return parsed_data.get("external_item_id")
        return parsed_data.get("account_id")

    async def _process_batch(
        self,
        connector: ItemContextConnector,
        import_record: ItemContextImport,
        batch: list[dict],
    ) -> dict[str, int]:
        """Process a batch of records."""
        stats = {"matched": 0, "applied": 0, "not_found": 0, "error": 0}

        # Collect all match IDs
        match_ids = [item["match_id"] for item in batch]

        # Query matching CheckItems
        if connector.match_by_external_item_id:
            query = select(CheckItem).where(
                CheckItem.tenant_id == connector.tenant_id,
                CheckItem.external_item_id.in_(match_ids)
            )
        else:
            query = select(CheckItem).where(
                CheckItem.tenant_id == connector.tenant_id,
                CheckItem.account_id.in_(match_ids)
            )

        result = await self.db.execute(query)
        check_items = {
            (ci.external_item_id if connector.match_by_external_item_id else ci.account_id): ci
            for ci in result.scalars().all()
        }

        # Apply context to matched items
        for item in batch:
            check_item = check_items.get(item["match_id"])

            if not check_item:
                stats["not_found"] += 1
                await self._create_error_record(
                    import_record, item["row_num"], RecordStatus.NOT_FOUND,
                    item["parsed_data"],
                    f"No CheckItem found for {connector.match_field}: {item['match_id']}"
                )
                continue

            stats["matched"] += 1

            # Apply context fields
            try:
                applied = await self._apply_context(
                    connector, check_item, item["parsed_data"]
                )
                if applied:
                    stats["applied"] += 1
            except Exception as e:
                stats["error"] += 1
                await self._create_error_record(
                    import_record, item["row_num"], RecordStatus.ERROR,
                    item["parsed_data"], str(e),
                    check_item_id=check_item.id
                )

        await self.db.commit()
        return stats

    async def _apply_context(
        self,
        connector: ItemContextConnector,
        check_item: CheckItem,
        parsed_data: dict[str, Any],
    ) -> bool:
        """Apply context data to a CheckItem."""
        # Check if we should update existing context
        if not connector.update_existing and check_item.account_tenure_days is not None:
            return False

        # Apply each context field
        updated = False
        for field_name, field_config in CONTEXT_FIELDS.items():
            if field_name in parsed_data and parsed_data[field_name] is not None:
                column_name = field_config["column"]
                setattr(check_item, column_name, parsed_data[field_name])
                updated = True

        return updated

    async def _create_error_record(
        self,
        import_record: ItemContextImport,
        row_num: int,
        status: RecordStatus,
        parsed_data: dict[str, Any],
        error_message: str,
        check_item_id: str | None = None,
    ) -> None:
        """Create an error record for tracking."""
        record = ItemContextImportRecord(
            id=str(uuid.uuid4()),
            import_id=import_record.id,
            row_number=row_num,
            status=status,
            account_id_from_file=parsed_data.get("account_id"),
            external_item_id_from_file=parsed_data.get("external_item_id"),
            check_item_id=check_item_id,
            context_data=parsed_data,
            error_message=error_message,
        )
        self.db.add(record)

    async def _handle_processed_file(
        self,
        sftp: SFTPService,
        connector: ItemContextConnector,
        sftp_file: SFTPFile,
        import_status: ImportStatus,
    ) -> None:
        """Move or delete processed file on SFTP server."""
        try:
            if import_status in (ImportStatus.COMPLETED, ImportStatus.PARTIAL):
                # Success - archive or delete
                if connector.sftp_archive_path:
                    archive_path = f"{connector.sftp_archive_path}/{sftp_file.name}"
                    await sftp.move_file(sftp_file.path, archive_path)
                else:
                    await sftp.delete_file(sftp_file.path)
            else:
                # Failed - move to error path if configured
                if connector.sftp_error_path:
                    error_path = f"{connector.sftp_error_path}/{sftp_file.name}"
                    await sftp.move_file(sftp_file.path, error_path)
        except Exception:
            # Don't fail the import if file handling fails
            pass

    async def get_import_history(
        self,
        connector_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ItemContextImport]:
        """Get import history for a connector."""
        query = (
            select(ItemContextImport)
            .where(ItemContextImport.connector_id == connector_id)
            .order_by(ItemContextImport.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_import_errors(
        self,
        import_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ItemContextImportRecord]:
        """Get error records for an import."""
        query = (
            select(ItemContextImportRecord)
            .where(
                ItemContextImportRecord.import_id == import_id,
                ItemContextImportRecord.status.in_([
                    RecordStatus.NOT_FOUND,
                    RecordStatus.INVALID,
                    RecordStatus.ERROR,
                ])
            )
            .order_by(ItemContextImportRecord.row_number)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
