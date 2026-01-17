"""
Demo mode item resolver.

Resolves check items using a JSON or SQLite index file.
"""
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from ..interfaces import (
    ItemResolver,
    ImageHandle,
    ItemMetadata,
    ImageSide,
    ItemNotFoundError,
)
from ...core.config import get_settings


class DemoItemResolver(ItemResolver):
    """
    Item resolver for demo mode.

    Uses a JSON index file to map (trace, date) pairs to image handles
    and metadata.

    Index file format:
    {
        "items": [
            {
                "trace_number": "12374628",
                "date": "2024-01-15",
                "image_path": "\\\\tn-director-pro\\Checks\\Transit\\V406\\580\\12374628.IMG",
                "amount_cents": 125000,
                "check_number": "1234",
                "account_last4": "5678",
                "is_onus": false,
                "is_multi_page": true,
                "has_back_image": true
            }
        ]
    }
    """

    def __init__(self, index_path: str = None):
        """
        Initialize the demo item resolver.

        Args:
            index_path: Path to the JSON index file.
                       Defaults to settings.ITEM_INDEX_PATH
        """
        settings = get_settings()
        self._index_path = Path(index_path or settings.ITEM_INDEX_PATH)
        self._items: Dict[str, ItemMetadata] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()

    def _make_key(self, trace_number: str, check_date: date) -> str:
        """Create a lookup key from trace number and date."""
        return f"{trace_number}:{check_date.isoformat()}"

    async def _ensure_loaded(self):
        """Load the index file if not already loaded."""
        if self._loaded:
            return

        async with self._load_lock:
            if self._loaded:
                return

            await self._load_index()
            self._loaded = True

    async def _load_index(self):
        """Load items from the JSON index file."""
        if not self._index_path.exists():
            # No index file - will have empty items
            return

        def _read_file():
            with open(self._index_path, "r") as f:
                return json.load(f)

        try:
            data = await asyncio.get_event_loop().run_in_executor(None, _read_file)

            for item_data in data.get("items", []):
                metadata = self._parse_item(item_data)
                if metadata:
                    key = self._make_key(metadata.trace_number, metadata.check_date)
                    self._items[key] = metadata

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in index file: {e}")
        except Exception as e:
            raise IOError(f"Failed to load index file: {e}")

    def _parse_item(self, data: Dict[str, Any]) -> Optional[ItemMetadata]:
        """Parse an item from the JSON index."""
        try:
            # Parse date
            date_str = data.get("date")
            if isinstance(date_str, str):
                check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                check_date = date_str

            # Get image path
            image_path = data.get("image_path", "")
            is_multi_page = data.get("is_multi_page", True)
            has_back = data.get("has_back_image", True)

            # Create image handle
            handle = ImageHandle(
                path=image_path,
                trace_number=data.get("trace_number"),
                check_date=check_date,
                is_multi_page=is_multi_page,
                page_count=2 if is_multi_page and has_back else 1
            )

            return ItemMetadata(
                trace_number=data.get("trace_number", ""),
                check_date=check_date,
                amount_cents=data.get("amount_cents", 0),
                check_number=data.get("check_number"),
                account_last4=data.get("account_last4", "****"),
                is_onus=data.get("is_onus", False),
                image_handle=handle,
                has_back_image=has_back
            )
        except Exception:
            return None

    async def resolve(
        self,
        trace_number: str,
        check_date: date
    ) -> Optional[ItemMetadata]:
        """
        Resolve a check item by trace number and date.

        Args:
            trace_number: The check's trace number
            check_date: The date of the check

        Returns:
            ItemMetadata if found, None otherwise
        """
        await self._ensure_loaded()
        key = self._make_key(trace_number, check_date)
        return self._items.get(key)

    async def get_image_handle(
        self,
        trace_number: str,
        check_date: date,
        side: ImageSide
    ) -> Optional[ImageHandle]:
        """
        Get the image handle for a specific side of a check.

        Args:
            trace_number: The check's trace number
            check_date: The date of the check
            side: Which side of the check (front or back)

        Returns:
            ImageHandle if found, None otherwise
        """
        metadata = await self.resolve(trace_number, check_date)
        if not metadata:
            return None

        # Check if back side is available
        if side == ImageSide.BACK and not metadata.has_back_image:
            return None

        return metadata.image_handle

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check if the item resolver is healthy.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            if not self._index_path.exists():
                return False, f"Index file not found: {self._index_path}"

            await self._ensure_loaded()
            item_count = len(self._items)
            return True, f"Demo resolver ready with {item_count} items"
        except Exception as e:
            return False, f"Resolver health check failed: {str(e)}"

    async def reload(self):
        """Force reload the index file."""
        self._loaded = False
        self._items.clear()
        await self._ensure_loaded()

    async def list_items(self) -> List[ItemMetadata]:
        """
        List all items in the index.

        Returns:
            List of all ItemMetadata
        """
        await self._ensure_loaded()
        return list(self._items.values())
