# engine/router.py

from collections import defaultdict
from typing import Callable, Dict, List, Any


EventHandler = Callable[[str, Dict[str, Any]], None]


class EventRouter:
    """
    Lightweight synchronous event bus.

    - Listeners subscribe to string topics, e.g. "battle.hit", "fx.skill".
    - Emit events with a topic + payload dict.
    - Designed to be engine-wide (battle, overworld, cinematics, etc.).
    """

    def __init__(self) -> None:
        self._listeners: Dict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """
        Register a handler for a given topic.

        handler(topic, payload_dict) will be called on emit().
        """
        self._listeners[topic].append(handler)

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        if topic in self._listeners:
            self._listeners[topic] = [
                h for h in self._listeners[topic] if h is not handler
            ]
            if not self._listeners[topic]:
                del self._listeners[topic]

    def emit(self, topic: str, **payload: Any) -> None:
        """
        Emit an event. All handlers for this topic will be invoked
        synchronously in registration order.
        """
        handlers = self._listeners.get(topic, [])
        event_data = dict(payload)

        for handler in handlers:
            handler(topic, event_data)
