import asyncio
import collections
import random
from datetime import datetime
from enum import Enum

DEFAULT_PROXY_TIME_OUT_ON_SUCCESS = random.randint(int(60 * 0.7), int(60 * 1.3))  # минута +- 30%
DEFAULT_PROXY_TIME_OUT_ON_ERROR = 15 * random.randint(int(60 * 0.7), int(60 * 1.3))  # 15 * (минута +- 30%)


class ProxyState(Enum):
    NEW = 0
    VALID = 1
    BANNED = 2
    UNAVAILABLE = 3


class Proxy:
    def __init__(self, address):
        self._address = address

        self._state = None
        self._state_history = []

        self.set_state(ProxyState.NEW)

    @property
    def address(self):
        return self._address

    def set_state(self, new_state: ProxyState):
        self._state = new_state
        self._state_history.append((new_state, datetime.now()))

    def get_states_history(self):
        return self._state_history


class ProxyManager:
    def __init__(self, proxy_list, time_out_success=None, time_out_error=None, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self._proxy_list = collections.deque(proxy_list)

        # proxy timeouts
        self._time_out_success = time_out_success or DEFAULT_PROXY_TIME_OUT_ON_SUCCESS
        self._time_out_error = time_out_error or DEFAULT_PROXY_TIME_OUT_ON_ERROR

        # Futures.
        self._getters = collections.deque()

    def empty(self):
        """
        Return True if the queue is empty, False otherwise.
        """
        return not self._proxy_list

    async def get(self) -> Proxy:
        """
        Remove and return an item from the queue.

        If queue is empty, wait until an item is available.

        This method is a coroutine.
        """
        while self.empty():
            getter = self._loop.create_future()
            self._getters.append(getter)
            try:
                await getter
            except Exception:
                getter.cancel()  # Just in case getter is not done yet.
                if not self.empty() and not getter.cancelled():
                    # We were woken up by put_nowait(), but can't take
                    # the call.  Wake up the next in line.
                    self._wakeup_getter()
                raise

        item = self._proxy_list.popleft()
        return item

    async def put(self, proxy: Proxy, timeout: int):
        if timeout > 0:
            await asyncio.sleep(timeout)

        self._proxy_list.append(proxy)
        self._wakeup_getter()

    def _release(self, proxy: Proxy, timeout: int = 0):
        asyncio.Task(self.put(proxy, timeout), loop=self._loop)

    def release_valid(self, proxy):
        proxy.set_state(ProxyState.VALID)
        self._release(proxy, timeout=self._time_out_success)

    def release_banned(self, proxy):
        proxy.set_state(ProxyState.BANNED)
        self._release(proxy, timeout=self._time_out_error)

    def release_unavailable(self, proxy):
        proxy.set_state(ProxyState.UNAVAILABLE)
        self._release(proxy, timeout=self._time_out_error)

    def _wakeup_getter(self):
        while self._getters:
            waiter = self._getters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                break
