from datetime import datetime
from typing import List, AsyncGenerator

from .internal_interface import InternalInterface
from ..external import MarketApi
from ..servers.endpoint import Endpoint, Method
from ... import History


class MarketInterface(InternalInterface):
    def __init__(self, market_api: MarketApi = None, host: str = None, headers: dict = None):
        super().__init__(host, headers)
        if market_api is None and host is None:
            raise ValueError("Executor or URL must be provided")
        self.market_api = market_api

    @Endpoint.http(Method.POST,
                   "/quote",
                   "Get quote data for a list of securities",
                   output=lambda response: History.from_dict(serialized=True, **response["data"]))
    def quote(self, tickers: List[str], start: datetime | str = None, end: datetime | str = None) -> dict:
        if self.market_api is None:
            raise ValueError("No market API provided")
        quotes = self.market_api.quote(tickers, start, end)

        response = {
            "status": "success",
            "data": quotes.to_dict(serializable=True),
        }

        return response

    @Endpoint.http(Method.POST,
                   "/historical",
                   "Get historical data for a list of securities",
                   output=lambda response: History.from_dict(serialized=True, **response["data"]))
    def historical(self, tickers: List[str], start: datetime | str, end: datetime | str) -> dict:
        if self.market_api is None:
            raise ValueError("No market API provided")
        history = self.market_api.historical(tickers, start, end)

        response = {
            "status": "success",
            "data": history.to_dict(serializable=True),
        }

        return response

    @Endpoint.websocket("/quote",
                        "Stream quotes for a list of securities",
                        output=lambda response: History.from_dict(serialized=True, **response)
                        )
    def quote_stream(self,
                     *args, **kwargs) -> AsyncGenerator:
        async def quote_stream():
            async for quote in self.market_api.quote_stream(*args, **kwargs):
                yield quote.to_dict(serializable=True)

        return quote_stream()
