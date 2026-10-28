"""Alpaca PAPER broker client. Refuses any non-paper base URL."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from core.agent import assert_paper_base_url
from core.secrets import AlpacaCreds, load_alpaca_creds


@dataclass
class PaperAccount:
    equity: float
    cash: float
    buying_power: float
    status: str
    account_number_masked: str


@dataclass
class PaperOrderResult:
    id: str
    symbol: str
    side: str
    qty: float
    status: str
    raw: dict[str, Any]


class AlpacaPaperBroker:
    """REST client bound to the paper endpoint only."""

    def __init__(self, creds: Optional[AlpacaCreds] = None) -> None:
        self.creds = creds or load_alpaca_creds()
        if self.creds is None:
            raise RuntimeError("Alpaca paper keys missing from environment")
        assert_paper_base_url(self.creds.base_url)

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | list[Any]:
        assert_paper_base_url(self.creds.base_url)  # type: ignore[union-attr]
        url = f"{self.creds.base_url}{path}"  # type: ignore[union-attr]
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "APCA-API-KEY-ID": self.creds.key_id,  # type: ignore[union-attr]
                "APCA-API-SECRET-KEY": self.creds.secret_key,  # type: ignore[union-attr]
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alpaca paper HTTP {exc.code}: {detail[:200]}") from exc

    def get_account(self) -> PaperAccount:
        data = self._request("GET", "/v2/account")
        assert isinstance(data, dict)
        acct = str(data.get("account_number", ""))
        masked = ("****" + acct[-4:]) if len(acct) >= 4 else "****"
        return PaperAccount(
            equity=float(data.get("equity") or 0),
            cash=float(data.get("cash") or 0),
            buying_power=float(data.get("buying_power") or 0),
            status=str(data.get("status") or ""),
            account_number_masked=masked,
        )

    def list_positions(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/v2/positions")
        assert isinstance(data, list)
        return data  # type: ignore[return-value]

    def submit_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        *,
        dry_run: bool = False,
    ) -> Optional[PaperOrderResult]:
        """Submit a fractional market order on the paper account.

        dry_run=True validates inputs and returns None without calling the API.
        """
        side_l = side.lower()
        if side_l not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if qty <= 0:
            raise ValueError("qty must be positive")
        # Hard cap: never send a single order above 50% of typical paper book
        # as an extra safety rail beyond Settings position_size.
        if qty > 10_000:
            raise ValueError("qty exceeds hard safety cap")
        body = {
            "symbol": symbol.upper(),
            "qty": f"{qty:.4f}",
            "side": side_l,
            "type": "market",
            "time_in_force": "day",
        }
        if dry_run:
            return None
        data = self._request("POST", "/v2/orders", body)
        assert isinstance(data, dict)
        return PaperOrderResult(
            id=str(data.get("id") or ""),
            symbol=str(data.get("symbol") or symbol),
            side=str(data.get("side") or side_l),
            qty=float(data.get("qty") or qty),
            status=str(data.get("status") or ""),
            raw=data,
        )
