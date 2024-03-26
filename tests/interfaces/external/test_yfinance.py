import asyncio
import time
import unittest

import dxlib as dx
import dxlib.interfaces.external.yfinance as yfinance


class TestYFinanceApi(unittest.TestCase):
    def setUp(self) -> None:
        self.api = yfinance.YFinanceAPI()

    def test_version(self):
        self.assertEqual(self.api.version, "1.0")

    def test_quotes(self):
        quotes = self.api.quote(["AAPL", "MSFT"])

        self.assertEqual(len(quotes), 2)
        self.assertEqual(set(quotes.df.index.names), {"date", "security"})

    def test_historical(self):
        today = dx.Date.today()
        last_week = dx.Date.prevdays(6)
        history = self.api.historical(["AAPL", "MSFT"], last_week, today)

        self.assertEqual(set(history.df.index.names), {"date", "security"})


class TestYFinanceInterface(unittest.TestCase):
    server = None
    websocket = None
    interface = None

    @classmethod
    def setUpClass(cls) -> None:
        logger = dx.DebugLogger()
        cls.server = dx.servers.HTTPServer(logger=logger)
        cls.websocket = dx.servers.WebsocketServer(logger=logger)
        cls.interface = dx.interfaces.MarketInterface(yfinance.YFinanceAPI(), host=cls.server.host)
        cls.server.add_interface(cls.interface)
        cls.websocket.add_interface(cls.interface)

        cls.server.start()
        cls.websocket.start()
        while not (cls.server.alive and cls.websocket.alive):
            time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()
        cls.websocket.stop()
        while cls.server.alive or not cls.websocket.stopped:
            time.sleep(0.1)

    def test_quote(self):
        today = dx.Date.today()
        last_week = dx.Date.prevdays(6)
        args = {
            "tickers": ["AAPL", "MSFT"],
            "start": last_week.strftime("%Y-%m-%d"),
            "end": today.strftime("%Y-%m-%d"),
        }
        quotes = self.interface.request(self.interface.quote, port=self.server.port, json=args)
        data = quotes["data"]
        quotes = dx.History.from_dict(serialized=True, **data)

        self.assertEqual(len(quotes), 2)
        self.assertEqual(set(quotes.df.index.names), {"date", "security"})

    def test_stream_quote(self):
        args = {
            "tickers": ["BTC-USD"],
            "interval": 5
        }

        self.websocket.listen(self.interface.quote_stream, **args)
        ws, quotes = self.interface.listen(self.interface.quote_stream, port=self.websocket.port)

        # quotes is an async generator
        # print accordingly (async loop)
        async def print_quotes():
            # asyncio wait for next
            quote = await quotes.__anext__()
            self.assertIsInstance(quote, dx.History)
            return

        # asyncio run
        asyncio.run(print_quotes())
        ws.close()

        # stop future
        # future.cancel()
        #
        # wait for future
        # while not future.done():
        #     time.sleep(0.1)


if __name__ == '__main__':
    unittest.main()
