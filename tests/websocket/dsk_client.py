"""Minimal obs-websocket v5 client used by the Downstream Keyer test scripts.

The password is read from the OBS_WS_PASSWORD environment variable and is never printed.
OBS_WS_PORT overrides the default port (4455).
"""
import asyncio
import base64
import hashlib
import json
import os
import uuid

import websockets

VENDOR = "downstream-keyer"
VENDOR_EVENTS = 512


class ObsClient:
    def __init__(self, ws):
        self.ws = ws
        self.events = []
        self._pending = {}
        self._reader = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls):
        port = int(os.environ.get("OBS_WS_PORT", "4455"))
        ws = await websockets.connect(f"ws://127.0.0.1:{port}", max_size=None)
        hello = json.loads(await ws.recv())["d"]
        identify = {"rpcVersion": 1, "eventSubscriptions": VENDOR_EVENTS}
        if "authentication" in hello:
            auth = hello["authentication"]
            password = os.environ.get("OBS_WS_PASSWORD", "")
            secret = base64.b64encode(hashlib.sha256((password + auth["salt"]).encode()).digest()).decode()
            identify["authentication"] = base64.b64encode(
                hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
        await ws.send(json.dumps({"op": 1, "d": identify}))
        if json.loads(await ws.recv())["op"] != 2:
            raise RuntimeError("identification refused")
        return cls(ws)

    async def _read(self):
        try:
            async for raw in self.ws:
                message = json.loads(raw)
                if message["op"] == 5 and message["d"]["eventType"] == "VendorEvent":
                    self.events.append(message["d"]["eventData"])
                elif message["op"] == 7:
                    future = self._pending.pop(message["d"]["requestId"], None)
                    if future and not future.done():
                        future.set_result(message["d"])
        except websockets.ConnectionClosed:
            pass
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("connection closed"))

    def send(self, request_type, data=None):
        """Sends a request without waiting; returns a future for its response."""
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        payload = {"requestType": request_type, "requestId": request_id, "requestData": data or {}}
        asyncio.ensure_future(self.ws.send(json.dumps({"op": 6, "d": payload})))
        return future

    async def request(self, request_type, data=None, timeout=10):
        return await asyncio.wait_for(self.send(request_type, data), timeout)

    def send_vendor(self, request_type, data=None):
        return self.send("CallVendorRequest", {
            "vendorName": VENDOR, "requestType": request_type,
            "requestData": {"view_name": "", **(data or {})}})

    async def vendor(self, request_type, data=None, timeout=10):
        response = await asyncio.wait_for(self.send_vendor(request_type, data), timeout)
        if not response["requestStatus"]["result"]:
            raise RuntimeError(f"{request_type}: {response['requestStatus']}")
        return response["responseData"]["responseData"]

    def events_of(self, event_type):
        return [e for e in self.events if e["eventType"] == event_type]

    async def close(self):
        await self.ws.close()
        self._reader.cancel()
