#
# Copyright (c) 2026
#
# SPDX-License-Identifier: BSD-2-Clause
#

import asyncio
from dataclasses import dataclass

import pytest


@dataclass
class _TestParams:
    serializer: object | None = None
    session_timeout: float | None = None


class _FakeClient:
    """Minimal stub of FastAPIWebsocketClient used by FastAPIWebsocketInputTransport."""

    def __init__(self, websocket):
        self._websocket = websocket
        self.is_closing = False
        self.disconnected = asyncio.Event()

    async def trigger_client_disconnected(self):
        self.disconnected.set()


class _FakeSerializer:
    def __init__(self):
        self.messages: list[bytes | str] = []

    async def deserialize(self, message):
        self.messages.append(message)
        return None


class _FakeWebSocket:
    def __init__(self, events):
        self._events = list(events)

    async def receive(self):
        await asyncio.sleep(0)
        return self._events.pop(0)


@pytest.mark.anyio
async def test_receive_messages_handles_text_then_bytes():
    """Regression: client sends TEXT start JSON then binary audio. We must not crash."""

    from bot_engine.transports.websocket.fastapi import FastAPIWebsocketInputTransport

    # Build a transport instance without calling its full __init__.
    transport = object.__new__(FastAPIWebsocketInputTransport)
    # The base classes expect a name for __str__/logging.
    transport._name = "FastAPIWebsocketInputTransport#test"

    serializer = _FakeSerializer()
    websocket = _FakeWebSocket(
        [
            {"type": "websocket.receive", "text": '{"type":"start"}'},
            {"type": "websocket.receive", "bytes": b"\x80\x3e\x00\x00"},
            {"type": "websocket.disconnect"},
        ]
    )

    transport._params = _TestParams(serializer=serializer, session_timeout=None)
    transport._client = _FakeClient(websocket)

    # Prevent push_frame/push_audio_frame from doing anything.
    async def _noop(*_args, **_kwargs):
        return None

    transport.push_frame = _noop
    transport.push_audio_frame = _noop

    # Run receive loop; it should exit cleanly (not raise).
    await transport._receive_messages()

    assert serializer.messages == ['{"type":"start"}', b"\x80\x3e\x00\x00"]
