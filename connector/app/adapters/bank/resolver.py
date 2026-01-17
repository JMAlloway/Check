"""
Bank mode (production) item resolver.

Resolves check items using the bank's item feed or index.

NOTE: This is a stub implementation. Real implementation requires:
- Integration with bank's core banking system or data warehouse
- Secure database connection or API client
- Proper error handling for bank-specific error codes
"""
from datetime import date
from typing import Optional, Tuple

from ..interfaces import ItemResolver, ImageHandle, ItemMetadata, ImageSide


class BankItemResolver(ItemResolver):
    """
    Item resolver for production bank mode.

    Queries the bank's item feed, data warehouse, or core system
    to resolve check items.

    STUB IMPLEMENTATION - Real implementation notes:
    - Connect to bank's item index (SQL Server, Oracle, etc.)
    - Or call bank's API for item resolution
    - Handle bank-specific error codes
    - Implement caching for performance
    - Support pagination for bulk queries
    """

    def __init__(
        self,
        connection_string: str = None,
        api_endpoint: str = None
    ):
        """
        Initialize the bank item resolver.

        Args:
            connection_string: Database connection string
            api_endpoint: Alternative API endpoint for resolution
        """
        raise NotImplementedError(
            "BankItemResolver is a stub. Production implementation required."
        )

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
        # Production implementation would:
        # 1. Query bank's item index by trace number and date
        # 2. Build UNC path from Director-style storage location
        # 3. Return ItemMetadata with all fields populated
        raise NotImplementedError(
            "BankItemResolver.resolve() requires production implementation"
        )

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
            side: Which side of the check

        Returns:
            ImageHandle if found, None otherwise
        """
        raise NotImplementedError(
            "BankItemResolver.get_image_handle() requires production implementation"
        )

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check connectivity to the bank's item index.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        return False, "BankItemResolver is a stub implementation"


# Production implementation example structure:
#
# class BankItemResolverImpl(ItemResolver):
#     """
#     Production implementation using bank's SQL Server database.
#     """
#
#     def __init__(self, config: BankResolverConfig):
#         self._pool = create_connection_pool(config.connection_string)
#
#     async def resolve(
#         self,
#         trace_number: str,
#         check_date: date
#     ) -> Optional[ItemMetadata]:
#         async with self._pool.acquire() as conn:
#             row = await conn.fetchrow(
#                 """
#                 SELECT
#                     trace_number,
#                     check_date,
#                     amount,
#                     check_number,
#                     RIGHT(account_number, 4) as account_last4,
#                     onus_flag,
#                     image_path,
#                     page_count
#                 FROM check_items
#                 WHERE trace_number = $1 AND check_date = $2
#                 """,
#                 trace_number,
#                 check_date
#             )
#             if not row:
#                 return None
#
#             return ItemMetadata(
#                 trace_number=row['trace_number'],
#                 check_date=row['check_date'],
#                 amount_cents=int(row['amount'] * 100),
#                 check_number=row['check_number'],
#                 account_last4=row['account_last4'],
#                 is_onus=row['onus_flag'] == 'O',
#                 image_handle=ImageHandle(
#                     path=row['image_path'],
#                     is_multi_page=row['page_count'] > 1,
#                     page_count=row['page_count']
#                 ),
#                 has_back_image=row['page_count'] > 1
#             )
