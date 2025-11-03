import os
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, Tuple
import inspect


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
        Set leverage for a perp market. Try multiple SDK signatures to ensure compatibility.
        Raises on failure; caller may decide whether to continue.
        """
        is_cross = (mode == "cross")
        lev_int = int(leverage)

        # Resolve asset index using meta when available
        asset_index = None
        try:
            asset_index = self._get_asset_index(coin)
        except Exception:
            pass

        # 1) Prefer the documented SDK signature: update_leverage(leverage, coin, is_cross=True)
        for name in ("update_leverage", "updateLeverage"):
            fn = getattr(self.exchange, name, None)
            if fn is None or not callable(fn):
                continue

            try:
                # Positional order per examples: (leverage, coin, is_cross)
                result = fn(lev_int, coin, is_cross)
                print(f"✅ Leverage set to {lev_int}x ({'cross' if is_cross else 'isolated'}) for {coin} via {name}(lev, coin, is_cross)")
                return result
            except TypeError:
                # Fall through to robust introspection-based kwargs approach
                pass
            except Exception as e:
                last_error = e
                # Try the next variant
                pass

        # 2) Robust fallback: introspect signature and supply only matching kwargs/args
        for name in ("update_leverage", "updateLeverage"):
            fn = getattr(self.exchange, name, None)
            if fn is None or not callable(fn):
                continue
            try:
                sig = inspect.signature(fn)
            except Exception:
                sig = None

            kwargs: Dict[str, Any] = {}
            if sig is not None:
                params = [p.name for p in sig.parameters.values() if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
                name_map: Dict[str, Any] = {
                    "leverage": lev_int,
                    "coin": coin,
                    "symbol": coin,
                    "market": coin,
                    "asset": asset_index,
                    "asset_index": asset_index,
                    "is_cross": is_cross,
                    "isCross": is_cross,
                    "cross": is_cross,
                }
                for p in params:
                    if p in name_map and name_map[p] is not None:
                        kwargs[p] = name_map[p]
            else:
                # If we cannot introspect, prefer asset index form
                if asset_index is not None:
                    kwargs = {"asset": asset_index, "is_cross": is_cross, "leverage": lev_int}
                else:
                    kwargs = {"coin": coin, "is_cross": is_cross, "leverage": lev_int}

            try:
                result = fn(**kwargs)
                print(f"✅ Leverage set to {lev_int}x ({'cross' if is_cross else 'isolated'}) for {coin} via {name}(**kwargs)")
                return result
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"Failed to set leverage for {coin}: {last_error if 'last_error' in locals() else 'no compatible method found'}")
    
    def _get_asset_index(self, coin: str) -> int:
        """Get the asset index for a coin symbol. Uses meta if available, otherwise tries common mappings."""
        try:
            meta = self.get_symbol_meta()
            # Try to find asset index in meta
            if "universe" in meta:
                for idx, asset in enumerate(meta["universe"]):
                    if isinstance(asset, dict):
                        name = asset.get("name", "").upper()
                    else:
                        name = str(asset).upper()
                    if name == coin.upper():
                        return idx
        except Exception:
            pass
        
        # Fallback: common asset indices (may need updates)
        common_indices = {
            "BTC": 0,
            "ETH": 1,
            "SOL": 2,
            "ARB": 3,
            "AVAX": 4,
        }
        
        if coin.upper() in common_indices:
            return common_indices[coin.upper()]
        
        # If we can't find it, raise error
        raise ValueError(f"Unable to determine asset index for {coin}. Check Hyperliquid meta or update mapping.")

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
        """
        Get available USDC balance for perps trading.
        Tries multiple paths in user_state response structure.
        """
        try:
            state = self.info.user_state(self.owner_address)
            
            # Debug: log structure for troubleshooting (first call only)
            if not hasattr(self, '_debug_logged_state'):
                import json
                state_str = json.dumps(state, indent=2)[:1000]  # First 1000 chars
                print(f"DEBUG user_state keys: {list(state.keys()) if isinstance(state, dict) else 'not dict'}")
                print(f"DEBUG user_state sample:\n{state_str}")
                self._debug_logged_state = True
            
            # Path 1: Check marginSummary nested structure
            if "marginSummary" in state and isinstance(state["marginSummary"], dict):
                margin_summary = state["marginSummary"]
                for key in ("withdrawable", "freeCollateral", "freeCollateralValue", "accountValue"):
                    if key in margin_summary:
                        try:
                            val = float(margin_summary[key])
                            if val > 0:
                                return val
                        except (ValueError, TypeError):
                            pass
            
            # Path 2: Check cross margin summary (if present)
            if "crossMaintenanceMarginUsed" in state and "accountValue" in state:
                try:
                    account_val = float(state["accountValue"])
                    margin_used = float(state.get("crossMaintenanceMarginUsed", 0))
                    # Available = account value - margin used
                    available = account_val - margin_used
                    if available > 0:
                        return available
                except (ValueError, TypeError):
                    pass
            
            # Path 3: Direct top-level fields
            for key in ("withdrawable", "freeCollateral", "freeCollateralValue"):
                if key in state:
                    try:
                        val = float(state[key])
                        if val > 0:
                            return val
                    except (ValueError, TypeError):
                        pass
            
            # Path 4: accountValue as fallback (total account value, not ideal but better than 0)
            if "accountValue" in state:
                try:
                    return float(state["accountValue"])
                except (ValueError, TypeError):
                    pass
            
            return 0.0  # Explicit 0 if nothing found
        except Exception as e:
            print(f"⚠️ Error fetching withdrawable USDC: {e}")
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
                # Handle nested position structure: { "position": { "coin": "...", "szi": ... } }
                pos_obj = pos.get("position", pos) if isinstance(pos, dict) else pos
                pos_coin = (pos_obj.get("coin") or pos_obj.get("asset") or pos_obj.get("symbol") or "").upper()
                if pos_coin == coin.upper():
                    # Common fields: szi (signed size), entryPx
                    size_raw = pos_obj.get("szi") or pos_obj.get("size") or 0.0
                    size = float(size_raw) if size_raw is not None else 0.0
                    entry = pos_obj.get("entryPx") or pos_obj.get("entryPrice")
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

        try:
            # Prefer SDK helper which submits limit IOC under the hood
            if hasattr(self.exchange, "market_open"):
                resp = self.exchange.market_open(coin, True, size)
            else:
                # Fallback: aggressive limit IOC a bit above mid
                mid = self.get_mid_price(coin)
                if not mid or mid <= 0:
                    raise RuntimeError("No mid price available")
                px = round(mid * 1.02, 6)
                resp = self.exchange.order(coin, True, size, px, {"limit": {"tif": "Ioc"}}, reduce_only=False)
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
            # Fallback to on-chain position size if provided size is invalid
            pos_sz, _ = self.get_position(coin)
            if pos_sz is not None and pos_sz > 0:
                size = self._round_size(coin, float(pos_sz))
            else:
                size = 0.0

        try:
            # Prefer SDK helper which submits reduce-only limit IOC
            if hasattr(self.exchange, "market_close"):
                # If size is still zero, let SDK close based on detected position
                if size and size > 0:
                    resp = self.exchange.market_close(coin, sz=size)
                else:
                    resp = self.exchange.market_close(coin)
            else:
                # Fallback: aggressive limit IOC a bit below mid
                mid = self.get_mid_price(coin)
                if not mid or mid <= 0:
                    raise RuntimeError("No mid price available")
                px = round(mid * 0.98, 6)
                # If size is still zero, attempt using full position size
                if not size or size <= 0:
                    pos_sz, _ = self.get_position(coin)
                    if pos_sz is not None and pos_sz > 0:
                        size = self._round_size(coin, float(pos_sz))
                    else:
                        size = 0.0
                if not size or size <= 0:
                    raise ValueError("No open position size found for reduce-only sell.")
                resp = self.exchange.order(coin, False, size, px, {"limit": {"tif": "Ioc"}}, reduce_only=True)
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


