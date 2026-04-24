from __future__ import annotations

from abc import ABC, abstractmethod
from argparse import _SubParsersAction


class ChannelProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def register(self, channel_subparsers: _SubParsersAction) -> None: ...

