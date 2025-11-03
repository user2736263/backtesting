import os
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, Tuple


try:
    # Official SDK modules (expected)
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
except Exception as _e:  # pragma: no cover
    # Defer hard failures until usage; allows repository import without SDK installed
    Info = None  # type: ignore
    Exchange = None  # type: ignore
    constants = None  # type: ignore


class HyperliquidAdapter:
    """
    Adapter for Hyperliquid perps using the Agent Wallet system.

    Responsibilities:
    - Connect (mainnet only per current plan)
    - Fetch market metadata and mid prices
    - Place market buy (open/increase long)
    - Place market sell (reduce-only) to close long
    - Read account state (withdrawable/account value) and current position
    - Manage leverage per market (cross by default)
    """

    def __init__(self, owner_address: str, agent_private_key: str, mainnet: bool = True) -> None:
        if Info is None or Exchange is None or constants is None:
            raise RuntimeError(
                "hyperliquid-python-sdk is required. Please `pip install hyperliquid-python-sdk`."
            )

        self.owner_address: str = owner_address
        self.agent_private_key: str = agent_private_key
        self.base_url: str = constants.MAINNET_API_URL if mainnet else constants.TESTNET_API_URL

        # Public data client
        self.info: Info = Info(self.base_url, skip_ws=True)

        # Trading client (signing with agent private key)
        # Some SDK versions accept (wallet, base_url, account_address=...)
        # Others accept (base_url, account_address, secret_key)
        # We try both for compatibility.
        self.exchange: Exchange = self._init_exchange()

        # Cached market meta
        self._meta: Optional[Dict[str, Any]] = None

    # ---- Initialization helpers -----------------------------------------------------------------
    def _init_exchange(self) -> Exchange:
        # Attempt constructor variant: Exchange(base_url, account_address, secret_key)
        try:
            return Exchange(self.base_url, self.owner_address, self.agent_private_key)  # type: ignore[arg-type]
        except Exception:
            # Attempt constructor variant: Exchange(wallet, base_url, account_address=...)
            try:
                # Lazy import to avoid hard dependency on eth_account if not needed
                from eth_account import Account  # type: ignore

                wallet = Account.from_key(self.agent_private_key)
                return Exchange(wallet, self.base_url, account_address=self.owner_address)  # type: ignore
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Hyperliquid Exchange client: {e}")

    # ---- Public methods -------------------------------------------------------------------------
    def set_leverage(self, coin: str, leverage: float, mode: str = "cross") -> None:
        """
        Set leverage for a perp market. Cross is default; isolated may require additional args
        depending on SDK version. Non-critical - gracefully handles SDK variations.
        """
        # Try common method names across SDK versions
        try:
            if hasattr(self.exchange, "update_leverage"):
                # Try with is_cross parameter (newer SDK versions)
                try:
                    self.exchange.update_leverage(coin, int(leverage), is_cross=(mode == "cross"))
                    return
                except TypeError:
                    # Fallback: try without is_cross parameter
                    self.exchange.update_leverage(coin, int(leverage))
                    return
            if hasattr(self.exchange, "updateLeverage"):
                self.exchange.updateLeverage(coin, int(leverage))
                return
        except Exception as e:
            # Log but don't crash - leverage can be set manually in UI
            print(f"⚠️ Leverage update failed (non-critical): {e}")
            print(f"   Set leverage manually in Hyperliquid UI for {coin} if needed.")
            return

        # If we reach here, SDK doesn't expose leverage update - not critical
        print(f"⚠️ SDK doesn't expose leverage update method.")
        print(f"   Set leverage manually in Hyperliquid UI for {coin} if needed.")

    def get_symbol_meta(self) -> Dict[str, Any]:
        """Return cached market meta; fetch once from Info if needed."""
        if self._meta is None:
            # Try common meta fetch patterns
            try:
                if hasattr(self.info, "meta"):
                    self._meta = self.info.meta()  # type: ignore[assignment]
                else:
                    # Fallback: some SDKs provide perp meta on info via a different call
                    # Use a generic call to trigger server-provided metadata.
                    # If unavailable, set empty meta and rely on sane defaults downstream.
                    self._meta = {}
            except Exception:
                self._meta = {}
        return self._meta or {}

    def _resolve_size_increment(self, coin: str) -> Decimal:
        """Derive size increment Decimal from meta; fallback to 0.001 if unknown."""
        meta = self.get_symbol_meta()
        # Heuristic: meta structures often include coin configs under perpMeta/coins with szDecimals or sizeIncrement
        try:
            perp_meta = meta.get("perpMeta") or meta.get("perp_meta") or {}
            coins = perp_meta.get("coins") or []
            for c in coins:
                sym = c.get("name") or c.get("coin") or c.get("symbol")
                if isinstance(sym, str) and sym.upper() == coin.upper():
                    if "sizeIncrement" in c:
                        return Decimal(str(c["sizeIncrement"]))
                    if "szDecimals" in c:
                        decimals = int(c["szDecimals"])  # e.g., 3 → 0.001
                        return Decimal(10) ** Decimal(-decimals)
        except Exception:
            pass
        return Decimal("0.001")

    def _round_size(self, coin: str, size: float) -> float:
        inc = self._resolve_size_increment(coin)
        quantized = Decimal(size).quantize(inc, rounding=ROUND_DOWN)
        return float(quantized)

    def get_mid_price(self, coin: str) -> Optional[float]:
        try:
            mids = self.info.all_mids()
            # all_mids: {"SOL": 185.12, ...}
            if isinstance(mids, dict):
                val = mids.get(coin.upper())
                return float(val) if val is not None else None
            return None
        except Exception:
            return None

    def get_account_value_usdc(self) -> Optional[float]:
        try:
            state = self.info.user_state(self.owner_address)
            # Common fields: accountValue, withdrawable, maybe freeCollateral
            for key in ("withdrawable", "freeCollateral", "accountValue"):
                if key in state:
                    try:
                        return float(state[key])
                    except Exception:
                        pass
            return None
        except Exception:
            return None

    def get_withdrawable_usdc(self) -> Optional[float]:
        try:
            state = self.info.user_state(self.owner_address)
            for key in ("withdrawable", "freeCollateral"):
                if key in state:
                    try:
                        return float(state[key])
                    except Exception:
                        pass
            # Fallback to accountValue if no explicit withdrawable field is present
            if "accountValue" in state:
                return float(state["accountValue"])  # type: ignore
            return None
        except Exception:
            return None

    def get_position(self, coin: str) -> Tuple[float, Optional[float]]:
        """
        Return (position_size_base, entry_price) for the coin. If no position, returns (0.0, None).
        """
        try:
            state = self.info.user_state(self.owner_address)
            # Try common shapes for positions
            candidates = []
            for key in ("assetPositions", "positions", "perpPositions"):
                if key in state and isinstance(state[key], list):
                    candidates = state[key]
                    break
            for pos in candidates:
                pos_coin = (pos.get("coin") or pos.get("asset") or pos.get("symbol") or "").upper()
                if pos_coin == coin.upper():
                    # Common fields: szi (signed size), entryPx
                    size = float(pos.get("szi") or pos.get("size") or 0.0)
                    entry = pos.get("entryPx") or pos.get("entryPrice")
                    entry_f = float(entry) if entry is not None else None
                    return size, entry_f
            return 0.0, None
        except Exception:
            return 0.0, None

    def place_market_buy(self, coin: str, size_base: float) -> Tuple[float, float]:
        """
        Place a market buy to open/increase a long.
        Returns (avg_fill_price, filled_size).
        """
        size = self._round_size(coin, size_base)
        if size <= 0:
            raise ValueError("Requested market buy size rounds to zero based on sizeIncrement.")

        # Use IOC market order; SDKs typically encode market orders with tif=Ioc
        order_spec = {"market": {"tif": "Ioc"}}

        try:
            # Common signature: order(coin, is_buy, size, price, order_type)
            resp = self.exchange.order(coin, True, size, 0.0, order_spec)  # type: ignore[attr-defined]
            return self._extract_avg_fill(resp)
        except Exception as e:
            raise RuntimeError(f"Market buy failed: {e}")

    def place_market_sell_reduce_only(self, coin: str, size_base: float) -> Tuple[float, float]:
        """
        Place a market sell reduce-only to close a long.
        Returns (avg_fill_price, filled_size).
        """
        size = self._round_size(coin, size_base)
        if size <= 0:
            raise ValueError("Requested market sell size rounds to zero based on sizeIncrement.")

        order_spec = {"market": {"tif": "Ioc", "reduceOnly": True}}

        try:
            resp = self.exchange.order(coin, False, size, 0.0, order_spec)  # type: ignore[attr-defined]
            return self._extract_avg_fill(resp)
        except Exception as e:
            raise RuntimeError(f"Reduce-only market sell failed: {e}")

    # ---- Response helpers -----------------------------------------------------------------------
    def _extract_avg_fill(self, resp: Any) -> Tuple[float, float]:
        """
        Try to extract (avg_price, filled_size) from a variety of SDK response shapes.
        Fallback to (mid_price, requested_size) if unavailable.
        """
        try:
            # Common shapes
            # 1) { "filled": [{ "px": 123.45, "sz": 0.5 }, ...] }
            if isinstance(resp, dict) and "filled" in resp and isinstance(resp["filled"], list):
                fills = resp["filled"]
                if fills:
                    total_sz = sum(float(f.get("sz", 0.0)) for f in fills)
                    if total_sz > 0:
                        vwap = sum(float(f.get("px", 0.0)) * float(f.get("sz", 0.0)) for f in fills) / total_sz
                        return float(vwap), float(total_sz)
            # 2) { "avgPx": 123.45, "filledSz": 0.5 }
            if isinstance(resp, dict) and "avgPx" in resp and "filledSz" in resp:
                return float(resp["avgPx"]), float(resp["filledSz"])
        except Exception:
            pass

        # Fallbacks
        mid = self.get_mid_price("SOL")  # small best-effort default; caller may ignore
        return float(mid or 0.0), 0.0


def from_env() -> "HyperliquidAdapter":
    """Factory that builds an adapter from environment variables (mainnet only)."""
    owner = os.getenv("HL_OWNER_ADDRESS")
    agent_pk = os.getenv("HL_AGENT_PRIVATE_KEY")
    if not owner or not agent_pk:
        raise RuntimeError("HL_OWNER_ADDRESS and HL_AGENT_PRIVATE_KEY must be set in environment.")
    return HyperliquidAdapter(owner, agent_pk, mainnet=True)


