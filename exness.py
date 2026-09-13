"""
Exness connection via MetaTrader 5.
Requires the MetaTrader5 package and a running MT5 terminal logged into an Exness account.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from config import cfg


class ExnessClient:
    def __init__(self):
        self.connected = False
        self.mt5 = None

    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
        except ImportError:
            print("[Exness] MetaTrader5 package not installed. pip install MetaTrader5")
            return False

        if cfg.mt5_path:
            init_ok = self.mt5.initialize(path=cfg.mt5_path)
        else:
            init_ok = self.mt5.initialize()

        if not init_ok:
            print(f"[Exness] initialize() failed: {self.mt5.last_error()}")
            return False

        if cfg.mt5_login and cfg.mt5_password and cfg.mt5_server:
            authorized = self.mt5.login(
                login=cfg.mt5_login,
                password=cfg.mt5_password,
                server=cfg.mt5_server,
            )
            if not authorized:
                print(f"[Exness] login failed: {self.mt5.last_error()}")
                self.mt5.shutdown()
                return False

        self.connected = True
        info = self.mt5.account_info()
        if info:
            print(f"[Exness] Connected — Balance: {info.balance} {info.currency} | Server: {info.server}")
        return True

    def disconnect(self):
        if self.mt5 and self.connected:
            self.mt5.shutdown()
            self.connected = False

    def account_info(self) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None
        info = self.mt5.account_info()
        if info is None:
            return None
        return info._asdict()

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        if not self.connected:
            return None
        info = self.mt5.symbol_info(symbol)
        return info._asdict() if info else None

    def get_tick(self, symbol: str) -> Optional[Dict]:
        if not self.connected:
            return None
        tick = self.mt5.symbol_info_tick(symbol)
        return tick._asdict() if tick else None

    def place_order(
        self,
        symbol: str,
        order_type: str,          # "BUY" or "SELL"
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "ai-agent",
    ) -> Dict[str, Any]:
        """Market order helper."""
        if not self.connected:
            return {"error": "not connected"}

        import MetaTrader5 as mt5
        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            return {"error": f"symbol {symbol} not found"}

        if not symbol_info.visible:
            self.mt5.symbol_select(symbol, True)

        tick = self.mt5.symbol_info_tick(symbol)
        price = tick.ask if order_type.upper() == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if order_type.upper() == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 20,
            "magic": 20260913,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp

        result = self.mt5.order_send(request)
        if result is None:
            return {"error": str(self.mt5.last_error())}
        return result._asdict()

    def positions(self) -> List[Dict]:
        if not self.connected:
            return []
        positions = self.mt5.positions_get()
        if positions is None:
            return []
        return [p._asdict() for p in positions]
