"""Tests must never touch the network (spec: zero network, zero keys)."""

import socket
from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def blocked(*_a: Any, **_k: Any) -> None:
        raise AssertionError("network access attempted in a test")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    yield
