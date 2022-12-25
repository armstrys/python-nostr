import threading
from .filter import Filters
from .message_pool import MessagePool
from .relay import Relay, RelayPolicy

class RelayManager:
    def __init__(self) -> None:
        self.relays: dict[str, Relay] = {}
        self.message_pool = MessagePool()

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
            print(f'connection open to {relay.url}')

    def close_connections(self):
        for relay in self.relays.values():
            relay.close()
            print(f'connection to {relay.url} closed')
    
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
