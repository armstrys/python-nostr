import threading
from .filter import Filters
from .message_pool import MessagePool
from .relay import Relay, RelayPolicy

class RelayManager:
    def __init__(self, allow_duplicates: bool = False) -> None:
        self.relays: dict[str, Relay] = {}
        self.message_pool = MessagePool(allow_duplicates=allow_duplicates)

    def __iter__(self):
        return iter(self.relays.values())

    def add_relay(self, url: str, read: bool=True, write: bool=True, subscriptions={}):
        policy = RelayPolicy(read, write)
        relay = Relay(url, policy, self.message_pool, subscriptions)
        self.relays[url] = relay

    def remove_relay(self, url: str):
        self.relays.pop(url)

    def add_subscription(self, id: str, filters: Filters):
        for relay in self.relays.values():
            relay.add_subscription(id, filters)

    def close_subscription(self, id: str):
        for relay in self.relays.values():
            relay.close_subscription(id)

    def open_connections(self, ssl_options: dict=None):
        for relay in self.relays.values():
            threading.Thread(
                target=relay.connect,
                args=(ssl_options,),
                name=f"{relay.url}-thread"
            ).start()

    def close_connections(self):
        for relay in self.relays.values():
            relay.close()
    
    @property
    def connection_statuses(self) -> dict:
        """gets the url and connection statuses of relays

        Returns:
            dict: bool of connection statuses
        """
        statuses = [relay.test_connection() for relay in self]
        urls = [relay.url for relay in self]
        return dict(zip(urls, statuses))
    
    def connection(self, *args, **kwargs):
        return Connection(self, *args, **kwargs)

    def publish_message(self, message: str):
        for relay in self.relays.values():
            if relay.policy.should_write:
                relay.publish(message)

class Connection:
    def __init__(self, relay_manager: RelayManager, *args, **kwargs):
        self.relay_manager = relay_manager
        self.conn = self.relay_manager.open_connections(*args, **kwargs)
    def __enter__(self):
        return self.conn
    def __exit__(self, type, value, traceback):
        self.relay_manager.close_connections()
