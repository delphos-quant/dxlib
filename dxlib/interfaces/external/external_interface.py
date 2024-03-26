from abc import ABC
from datetime import datetime
from typing import List, Dict, AsyncGenerator

import pandas as pd

from ..utils import Cache
from ...core import Schema, SchemaLevel, History, OrderData, Order, SecurityManager, Security, Signal


class ExternalInterface(ABC):

    def __init__(self):
        self.cache = Cache()


class MarketApi(ExternalInterface):
    @classmethod
    def to_history(cls,
                   df: pd.DataFrame,
                   levels: list = None,
                   fields: list = None,
                   security_manager: SecurityManager = None
                   ) -> History:
        schema = Schema(
            levels=[SchemaLevel.SECURITY, SchemaLevel.DATE] if levels is None else levels,
            fields=list(df.columns) if fields is None else fields,
            security_manager=security_manager
        )

        return History.from_df(df, schema)

    def historical(
            self,
            tickers: List[str] | str,
            start: datetime | str,
            end: datetime | str,
            timeframe="1d",
            cache=False,
    ) -> History:
        raise NotImplementedError

    def quote(
            self,
            tickers: List[str] | str,
            start: datetime | str = None,
            end: datetime | str = None,
            interval="1m",
            cache=False,
    ) -> History:
        raise NotImplementedError

    def quote_stream(self, *args, **kwargs) -> AsyncGenerator:
        raise NotImplementedError


class OrderInterface(ExternalInterface):
    def execute_order(self, order_data: OrderData) -> Order:
        return Order(order_data)

    def execute_orders(self, orders: List[OrderData]) -> List[Order]:
        return [self.execute_order(order) for order in orders]

    def map_signals(self, signals: Dict[Security, Signal]) -> List[OrderData]:
        return [OrderData.from_signal(signal, security) for security, signal in signals.items()]

    def map_history(self, history: History) -> History:  # History[Signal] -> History[OrderData]
        if SchemaLevel.SECURITY not in history.schema.levels:
            raise ValueError("Security level not found in history schema")
        security_level = history.schema.levels.index(SchemaLevel.SECURITY)
        schema = Schema(
            levels=[SchemaLevel.DATE],
            fields=["order_data"],
            security_manager=history.schema.security_manager
        )
        order_data = history.apply(lambda x: pd.Series({"order_data": OrderData.from_signal(x['signal'], x.name[security_level])}), axis=1, schema=schema)
        return order_data

    def execute_signals(self, signals: Dict[Security, Signal] | pd.Series) -> List[Order]:
        if isinstance(signals, pd.Series):
            signals = signals.to_dict()

        orders_data = self.map_signals(signals)
        return self.execute_orders(orders_data)

    def execute_history(self, history: History) -> History:  # History[Signal] -> History[Order]
        orders_data = self.map_history(history)

        schema = Schema(
            levels=[SchemaLevel.DATE],
            fields=["order"],
            security_manager=history.schema.security_manager
        )
        orders = orders_data.apply(lambda x: pd.Series({"order": self.execute_order(x['order_data'])}), schema=schema, axis=1)
        return orders

    @staticmethod
    def executed_quantity(order_history: History):
        return order_history.apply(lambda x: (x['order'].quantity or 0) * x['order'].side.value, axis=1)


class PortfolioInterface(ExternalInterface, ABC):
    def get(self, identifier=None):
        raise NotImplementedError

    def add(self, order, market):
        raise NotImplementedError

    def set(self, portfolio):
        raise NotImplementedError
