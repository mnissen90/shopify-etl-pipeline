"""Extract: Shopify REST API client.

Pulls orders day-by-day with Link-header pagination and retry-with-backoff,
yielding raw order dicts for the transform layer.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Iterator

import requests
from requests.auth import HTTPBasicAuth

from .retry import retry

logger = logging.getLogger(__name__)

ORDER_FIELDS = (
    "billing_address,source_name,refunds,created_at,discount_codes,id,"
    "order_number,name,email,customer,line_items,total-price,"
    "total_line_items_price,shipping_lines,tags"
)


class ShopifyClient:
    def __init__(
        self,
        store_name: str,
        api_key: str,
        api_password: str,
        api_version: str = "2020-10",
        max_retries: int = 3,
        backoff_seconds: int = 20,
    ) -> None:
        self.store_name = store_name
        self.api_version = api_version
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(api_key, api_password)
        self._fetch_page = retry(
            max_attempts=max_retries, backoff_seconds=backoff_seconds
        )(self._fetch_page_raw)

    @property
    def base_url(self) -> str:
        return (
            f"https://{self.store_name}.myshopify.com"
            f"/admin/api/{self.api_version}/orders.json"
        )

    def _fetch_page_raw(self, url: str, params: dict | None = None) -> requests.Response:
        response = self.session.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response

    @staticmethod
    def _next_link(response: requests.Response) -> str | None:
        """Parse the RFC 5988 Link header for the rel="next" URL."""
        link_header = response.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part or "next" in part.split(";")[0]:
                # format: <https://...>; rel="next"
                start = part.find("<") + 1
                end = part.find(">")
                if start > 0 and end > start:
                    return part[start:end]
        return None

    def fetch_orders(
        self, day: dt.date, updated_since: bool = False
    ) -> Iterator[dict]:
        """Yield every order for a single day, following pagination.

        Args:
            day: the calendar day to pull.
            updated_since: filter on updated_at instead of created_at
                (used for the refunds pass, which catches late adjustments).
        """
        date_key = "updated_at_min" if updated_since else "created_at_min"
        params = {
            date_key: str(day),
            date_key.replace("_min", "_max"): str(day + dt.timedelta(days=1)),
            "limit": "250",
            "status": "any",
            "fields": ORDER_FIELDS,
        }
        url: str | None = self.base_url
        first = True
        while url:
            response = self._fetch_page(url, params if first else None)
            first = False
            data = response.json()
            orders = data.get("orders", [])
            logger.info(
                "%s: fetched %d orders for %s (store=%s)",
                self.store_name,
                len(orders),
                day,
                self.store_name,
            )
            yield from orders
            url = self._next_link(response)
