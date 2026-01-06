"""Base interfaces for integration adapters.

These interfaces define the contract that all integration adapters must implement.
This allows the application to work with different core banking systems (Q2, Fiserv, etc.)
without changing the application logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class PresentedItem:
    """Standardized presented check item from external system."""

    external_item_id: str
    source_system: str
    account_id: str
    account_number_masked: str
    account_type: str
    routing_number: str | None
    check_number: str | None
    amount: Decimal
    currency: str
    payee_name: str | None
    memo: str | None
    micr_line: str | None
    micr_account: str | None
    micr_routing: str | None
    micr_check_number: str | None
    presented_date: datetime
    check_date: datetime | None
    front_image_id: str | None
    back_image_id: str | None
    upstream_flags: list[str] | None


@dataclass
class CheckImageData:
    """Check image data from external system."""

    image_id: str
    image_type: str  # "front" or "back"
    content: bytes
    content_type: str
    width: int | None
    height: int | None
    dpi: int | None


@dataclass
class AccountContext:
    """Account context information from external system."""

    account_id: str
    account_type: str
    account_tenure_days: int | None
    current_balance: Decimal | None
    average_balance_30d: Decimal | None
    relationship_id: str | None
    branch_code: str | None
    market_code: str | None


@dataclass
class CheckBehaviorStats:
    """Check behavior statistics from external system."""

    account_id: str
    avg_check_amount_30d: Decimal | None
    avg_check_amount_90d: Decimal | None
    avg_check_amount_365d: Decimal | None
    check_std_dev_30d: Decimal | None
    max_check_amount_90d: Decimal | None
    check_frequency_30d: int | None
    returned_item_count_90d: int | None
    exception_count_90d: int | None


@dataclass
class HistoricalCheck:
    """Historical check item from external system."""

    external_item_id: str
    account_id: str
    check_number: str | None
    amount: Decimal
    check_date: datetime
    payee_name: str | None
    status: str  # "cleared", "returned", etc.
    return_reason: str | None
    front_image_id: str | None
    back_image_id: str | None


class CheckItemProvider(ABC):
    """Interface for retrieving presented check items."""

    @abstractmethod
    async def get_presented_items(
        self,
        date_from: datetime,
        date_to: datetime,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        account_types: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PresentedItem], int]:
        """
        Retrieve presented check items within a date range.

        Args:
            date_from: Start of date range
            date_to: End of date range
            amount_min: Minimum amount filter
            amount_max: Maximum amount filter
            account_types: Filter by account types
            limit: Maximum number of items to return
            offset: Pagination offset

        Returns:
            Tuple of (items, total_count)
        """
        pass

    @abstractmethod
    async def get_item_by_id(self, external_item_id: str) -> PresentedItem | None:
        """Retrieve a specific presented item by ID."""
        pass


class CheckImageProvider(ABC):
    """Interface for retrieving check images."""

    @abstractmethod
    async def get_image(self, image_id: str) -> CheckImageData | None:
        """
        Retrieve a check image by ID.

        Args:
            image_id: External image identifier

        Returns:
            CheckImageData or None if not found
        """
        pass

    @abstractmethod
    async def get_image_url(self, image_id: str, expires_in: int = 60) -> str | None:
        """
        Get a signed URL for direct image access.

        Args:
            image_id: External image identifier
            expires_in: URL expiration in seconds

        Returns:
            Signed URL or None if not available
        """
        pass

    @abstractmethod
    async def get_thumbnail(
        self, image_id: str, width: int = 200, height: int = 100
    ) -> bytes | None:
        """
        Get a thumbnail version of the image.

        Args:
            image_id: External image identifier
            width: Thumbnail width
            height: Thumbnail height

        Returns:
            Thumbnail image bytes or None
        """
        pass


class AccountContextProvider(ABC):
    """Interface for retrieving account context."""

    @abstractmethod
    async def get_account_context(self, account_id: str) -> AccountContext | None:
        """
        Retrieve account context information.

        Args:
            account_id: Account identifier

        Returns:
            AccountContext or None if not found
        """
        pass

    @abstractmethod
    async def get_check_behavior_stats(self, account_id: str) -> CheckBehaviorStats | None:
        """
        Retrieve check behavior statistics for an account.

        Args:
            account_id: Account identifier

        Returns:
            CheckBehaviorStats or None if not found
        """
        pass


class CheckHistoryProvider(ABC):
    """Interface for retrieving historical check data."""

    @abstractmethod
    async def get_check_history(
        self,
        account_id: str,
        limit: int = 10,
        amount_range: tuple[Decimal, Decimal] | None = None,
        payee_name: str | None = None,
    ) -> list[HistoricalCheck]:
        """
        Retrieve historical checks for an account.

        Args:
            account_id: Account identifier
            limit: Maximum number of items to return
            amount_range: Optional (min, max) amount filter
            payee_name: Optional payee name filter

        Returns:
            List of historical checks
        """
        pass

    @abstractmethod
    async def get_similar_checks(
        self,
        account_id: str,
        amount: Decimal,
        payee_name: str | None = None,
        limit: int = 5,
    ) -> list[HistoricalCheck]:
        """
        Find similar historical checks for comparison.

        Args:
            account_id: Account identifier
            amount: Reference amount for similarity
            payee_name: Optional payee name for matching
            limit: Maximum number of items to return

        Returns:
            List of similar historical checks
        """
        pass
