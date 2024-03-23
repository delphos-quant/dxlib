import asyncio
import json
from abc import ABC
from typing import List, Tuple, AsyncGenerator

import requests
import websockets

from ..servers.endpoint import EndpointScheme, EndpointWrapper, Method


class InternalInterface(ABC):

    def __init__(self, host: str = None, headers: dict = None):
        self.host = host
        self.headers = headers or {}

        self.endpoints = {
            (endpoint_wrapper.route_name, endpoint_wrapper.method): endpoint_wrapper
            for endpoint_wrapper, _ in self.get_endpoints()
        }

    def get_endpoints(self, endpoint_scheme: EndpointScheme = None) -> List[Tuple[EndpointWrapper, callable]]:
        endpoints = []

        for func_name in dir(self):
            attr = self.__class__.__dict__.get(func_name)

            if callable(attr) and hasattr(attr, "endpoint") and (
                    endpoint_scheme is None or attr.endpoint.endpoint_scheme == endpoint_scheme):
                endpoint = attr.endpoint
                # noinspection PyUnresolvedReferences
                func = attr.__get__(self)
                endpoints.append((endpoint, func))

            elif isinstance(attr, property):
                if hasattr(attr.fget, "endpoint"):
                    endpoint = attr.fget.endpoint
                    if endpoint_scheme is not None and endpoint.endpoint_scheme != endpoint_scheme:
                        continue
                    # noinspection PyUnresolvedReferences
                    func = attr.fget.__get__(self, self.__class__)
                    endpoints.append((endpoint, func))

                if hasattr(attr.fset, "endpoint"):
                    endpoint = attr.fset.endpoint
                    if endpoint_scheme is not None and endpoint.endpoint_scheme != endpoint_scheme:
                        continue
                    # noinspection PyUnresolvedReferences
                    func = attr.fset.__get__(self, self.__class__)
                    endpoints.append((endpoint, func))

        return endpoints

    def make_url(self, wrapper: EndpointWrapper, port: int):
        return f"{wrapper.endpoint_scheme.value}://{self.host}:{port}{wrapper.route_name}"

    def request(self, function: any, port: int, *args, **kwargs):
        if self.host is None:
            raise ValueError("URL for interfacing must be provided on interface creation")

        wrapper: EndpointWrapper = function.endpoint
        url = self.make_url(wrapper, port)

        method = wrapper.method
        if method == Method.GET:
            request = requests.get
        elif method == Method.POST:
            request = requests.post
        elif method == Method.PUT:
            request = requests.put
        else:
            raise ValueError(f"Method {method} not supported")

        response = request(url, headers=self.headers, *args, **kwargs)

        if response.status_code != 200:
            raise ValueError(f"Request failed with status code {response.text}")

        if wrapper and wrapper.output is not None:
            return wrapper.output(response.json())
        else:
            return response.json()

    @staticmethod
    async def _listen_websocket(wrapper: EndpointWrapper, url: str, retries=3, delay=5) -> AsyncGenerator:
        attempt = 0
        while attempt <= retries:
            try:
                async with websockets.connect(url) as ws:
                    print("Connected to", url)
                    while True:
                        try:
                            message = await ws.recv()

                            if wrapper and wrapper.output is not None:
                                yield wrapper.output(json.loads(message))
                            else:
                                yield message
                        except websockets.ConnectionClosed:
                            print("Connection closed unexpectedly")
                            break
                print("Connection closed")
            except (websockets.ConnectionClosed, ConnectionRefusedError, ValueError) as e:
                print(f"Failed to connect to {url}: {e}")
                attempt += 1
                if attempt <= retries:
                    print(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise ConnectionRefusedError(f"Could not connect to {url} after {retries} attempts")
            except Exception as e:
                print(f"Failed to connect to {url}: {e}")
                raise

    def listen(self, function: any, port: int, retry=0) -> AsyncGenerator:
        if self.host is None:
            raise ValueError("URL for interfacing must be provided on interface creation")

        wrapper: EndpointWrapper = function.endpoint
        url = self.make_url(wrapper, port)

        if wrapper.endpoint_scheme == EndpointScheme.WEBSOCKET:
            # self._listen_websocket(wrapper, url, retry)
            return self._listen_websocket(wrapper, url, retry)
        elif wrapper.endpoint_scheme == EndpointScheme.TCP:
            raise NotImplementedError("TCP not supported yet")
        else:
            raise ValueError(f"Endpoint type {wrapper.endpoint_scheme} not supported")
