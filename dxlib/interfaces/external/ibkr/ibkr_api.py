import asyncio
import datetime
from typing import List, AsyncGenerator

import pandas as pd
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

from ....core import History, SecurityManager, Schema, SchemaLevel


class IBKR_API(EWrapper, EClient):
    def __init__(self, base_url=None):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self.base_url = base_url
        self.tickers = []

    @property
    def version(self):
        return "1.0"

    @property
    def header(self):
        return None

    @property
    def keepalive_header(self):
        return None

    @classmethod
    def format_response_data(cls, data):
        # Implement your logic to format the response data from IBKR API
        result = data['result']
        formatted_data = {
            "date": [datetime.datetime.fromtimestamp(ts) for ts in result['timestamp']],
            "open": result['open'],
            "high": result['high'],
            "low": result['low'],
            "close": result['close'],
            "volume": result['volume']
        }
        return formatted_data

    @classmethod
    def format_quote(cls, data):
        # Implement your logic to format the quote data from IBKR API
        return {
            "date": datetime.datetime.fromtimestamp(data['timestamp']),
            "price": data['price']
        }

    def quote_ticker(self, ticker, range_in="1d", interval="1m"):
        # Implement method to request quote data for a single ticker from IBKR API
        contract = Contract()
        contract.symbol = ticker
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        self.reqHistoricalData(0, contract, "", f"{range_in} ago", interval, "TRADES", 1, 1, False, [])
        self.tickers.append(ticker)

    def quote(
            self,
            tickers: List[str] | str,
            start: datetime | str = None,
            end: datetime | str = None,
            interval="1m",
            security_manager=None,
            cache=False,
    ) -> History:
        # Implement method to request quote data for multiple tickers from IBKR API
        tickers = [tickers] if isinstance(tickers, str) else tickers

        for ticker in tickers:
            self.quote_ticker(ticker)

        self.run()

        quotes = {}

        for ticker in self.tickers:
            data = self.data.pop(0)
            quotes[(data.pop("date"), ticker)] = data

        df = pd.DataFrame.from_dict(quotes, orient="index")
        return History(df, schema=Schema(
            levels=[SchemaLevel.DATE, SchemaLevel.SECURITY],
            fields=["price"],
            security_manager=security_manager if security_manager else SecurityManager.from_list(tickers)
        ))

    def historical(
            self,
            tickers: List[str] | str,
            start: datetime.datetime | str,
            end: datetime.datetime | str,
            timeframe="1d",
            cache=False,
    ) -> History:
        # Implement method to request historical data for multiple tickers from IBKR API
        tickers = [tickers] if isinstance(tickers, str) else tickers

        for ticker in tickers:
            contract = Contract()
            contract.symbol = ticker
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            self.reqHistoricalData(0, contract, "", f"{timeframe} ago", "1 day", "TRADES", 1, 1, False, [])

        self.run()

        quotes = {}

        for ticker in tickers:
            data = self.data.pop(0)
            quotes[(data.pop("date"), ticker)] = data

        df = pd.DataFrame.from_dict(quotes, orient="index")
        return History(df, schema=Schema(
            levels=[SchemaLevel.DATE, SchemaLevel.SECURITY],
            fields=["open", "high", "low", "close", "volume"],
        ))

    async def quote_stream(self, tickers: List[str], interval: int = 60) -> AsyncGenerator:
        # Implement method to stream real-time quotes from IBKR API
        contract = Contract()
        contract.symbol = ','.join(tickers)
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        self.reqMarketDataType(4)
        self.reqMktData(0, contract, "", False, False, [])
        self.run()

        while True:
            data = self.data.pop(0)
            yield data
            await asyncio.sleep(interval)
