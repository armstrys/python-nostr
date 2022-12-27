"""
a barebones client implementation based on python-nostr

TODO: add new features
 - websocket connection test: `_is_connected`
 - switch accounts
 - change relays with Client.connect and disconnect methods
 - figure out how to reset message pool or better deal with old requests?
 - continue filling out remaining core methods
"""

####### make sure python-nostr is accessible ###################
import sys
from pathlib import Path

sys.path.append(str(Path('../').resolve()))
assert 'python-nostr' in [Path(path).name for path in sys.path]
################################################################

import warnings
import json
import time
import os
import pprint

from nostr.key import PrivateKey, PublicKey
from nostr.relay_manager import RelayManager
from nostr.message_type import ClientMessageType
from nostr.message_pool import MessagePool, EventMessage,\
    NoticeMessage, EndOfStoredEventsMessage
from nostr.filter import Filter, Filters
from nostr.event import Event, EventKind


class Client:

    def __init__(self, public_key_hex: str = None, private_key_hex: str = None,
                 relay_urls: list = None, ssl_options: dict = {},
                 allow_duplicates: bool = False):
        """A basic framework for common operations that a nostr client will
        need to execute.

        Args:
            public_key_hex (str, optional): public key to initiate client
            private_key_hex (str, optional): private key to log in with public key.
                Defaults to None, in which case client is effectively read only
            relay_urls (list, optional): provide a list of relay urls.
                Defaults to None, in which case a default list will be used.
            ssl_options (dict, optional): ssl options for websocket connection
                Defaults to empty dict
            allow_duplicates (bool, optional): whether or not to allow duplicate
                event ids into the queue from multiple relays. This isn't fully
                working yet. Defaults to False.
        """
        self._is_connected = False
        self.ssl_options = ssl_options
        self.allow_duplicates = allow_duplicates
        self. set_account(public_key_hex=public_key_hex,
                          private_key_hex=private_key_hex)
        
        if relay_urls is None:
            relay_urls = [
                'wss://nostr-2.zebedee.cloud',
                # 'wss://nostr.zebedee.cloud',
                # 'wss://relay.damus.io',
            ]
        else:
            pass
        self.set_relays(relay_urls=relay_urls)
    
    def __enter__(self):
        """context manager to allow processing a connected client
        within a `with` statement

        Returns:
            self: a `with` statement returns this object as it's assignment
            so that the client can be instantiated and used within
            the `with` statement.
        """
        self.connect()
        return self

    def __exit__(self, type, value, traceback):
        """closes the connections when exiting the `with` context

        arguments are currently unused, but could be use to control
        client behavior on error.

        Args:
            type (_type_): _description_
            value (_type_): _description_
            traceback (_type_): _description_
        """
        self.disconnect()
        return traceback

    def connect(self) -> None:
        self.relay_manager.open_connections(self.ssl_options)
        time.sleep(2)
        self._is_connected = True
    
    def disconnect(self) -> None:
        time.sleep(2)
        self.relay_manager.close_connections()
        self._is_connected = False

    def set_account(self, public_key_hex: str = None, private_key_hex: str = None,):
        if public_key_hex is not None and private_key_hex is not None:
            self.private_key = PrivateKey.from_hex(private_key_hex)
            if public_key_hex != self.private_key.public_key.hex():
                raise Exception('private key does not match public key')
            self.public_key = self.private_key.public_key
        elif public_key_hex is None and private_key_hex is None:
            print('no keys provided. new account is being generated...')
            self.private_key = PrivateKey()
            self.public_key = self.private_key.public_key
        elif private_key_hex is not None:
            self.private_key = PrivateKey.from_hex(private_key_hex)
            self.public_key = self.private_key.public_key
        elif public_key_hex is not None:
            print('no private key provided. client initiated in read-only mode')
            self.public_key = PublicKey.from_hex(public_key_hex)
            self.private_key = None
    
    def set_relays(self, relay_urls: list = None):
        was_connected = self._is_connected
        if self._is_connected:
            self.disconnect()
        self.relay_manager = RelayManager(allow_duplicates=self.allow_duplicates)
        for url in relay_urls:
            self.relay_manager.add_relay(url=url)
        if was_connected:
            self.connect()
        

    @staticmethod
    def _event_handler(event_msg: EventMessage):
        """a hidden method used to handle event outputs
        from a relay. This can be overwritten to store events
        to a db for example.

        Args:
            event_msg (EventMessage): Event message returned from relay
        """
        pprint.pprint(event_msg.event.to_json_object(), indent=2)

    @staticmethod
    def _notice_handler(notice_msg: NoticeMessage):
        """a hidden method used to handle notice outputs
        from a relay. This can be overwritten to display notices
        differently - should be warnings or errors?

        Args:
            notice_msg (NoticeMessage): Notice message returned from relay
        """
        warnings.warn(notice_msg.content)

    @staticmethod
    def _eose_handler(eose_msg: EndOfStoredEventsMessage):
        """a hidden method used to handle notice outputs
        from a relay. This can be overwritten to display notices
        differently - should be warnings or errors?

        Args:
            notice_msg (EndOfStoredEventsMessage): Message from relay
                to signify the last event in a subscription has been
                provided.
        """
        print(f'end of subscription: {eose_msg.subscription_id} received.')

    def get_events_from_relay(self):
        """calls the _event_handler method on all events from relays
        """
        while self.relay_manager.message_pool.has_events():
            event_msg = self.relay_manager.message_pool.get_event()
            self._event_handler(event_msg=event_msg)

    def get_notices_from_relay(self):
        """calls the _notice_handler method on all notices from relays
        """
        while self.relay_manager.message_pool.has_notices():
            notice_msg = self.relay_manager.message_pool.get_notice()
            self._notice_handler(notice_msg=notice_msg)

    def get_eose_from_relay(self):
        """calls the _eose_handler end of subsribtion events from relays
        """
        while self.relay_manager.message_pool.has_eose_notices():
            eose_msg = self.relay_manager.message_pool.get_eose_notice()
            self._eose_handler(eose_msg=eose_msg)

    def publish_request(self, subscription_id: str, request_filters: Filters) -> None:
        """publishes a request from a subscription id and a set of filters. Filters
        can be defined using the request_by_custom_filter method or from a list of
        preset filters (as of yet to be created):

        Args:
            subscription_id (str): subscription id to be sent to relau
            request_filters (Filters): list of filters for a subscription
        """
        request = [ClientMessageType.REQUEST, subscription_id]
        request.extend(request_filters.to_json_array())
        message = json.dumps(request)
        self.relay_manager.add_subscription(
            subscription_id, request_filters
            )
        self.relay_manager.publish_message(message)
        time.sleep(1)
        self.get_events_from_relay()
        self.get_notices_from_relay()
        self.get_eose_from_relay()
    
    def publish_event(self, event: Event) -> None:
        """publish an event and immediately checks for a notice
        from the relay in case of an invalid event

        Args:
            event (Event): _description_
        """
        event.sign(self.private_key.hex())
        message = json.dumps([ClientMessageType.EVENT, event.to_json_object()])
        print(message)
        self.relay_manager.publish_message(message)
        time.sleep(1)
        self.get_notices_from_relay()

    def request_by_custom_filter(self, subscription_id, **filter_kwargs) -> None:
        """make a relay request from kwargs for a single Filter object
        as defined in python-nostr.filter.Filter

        Args:
            subscription_id (_type_): _description_
        Kwargs to follow python-nostr.filter.Filter
        """
        custom_request_filters = Filters([Filter(**filter_kwargs)])
        self.publish_request(
            subscription_id=subscription_id,
            request_filters=custom_request_filters
        )

######################### publish methods #######################
# establishing methods for all possible events outlined here:   #
# https://github.com/nostr-protocol/nips#event-kinds            #
#################################################################

    def publish_metadata(self) -> None:
        raise NotImplementedError()
    
    def publish_text_note(self, text: str) -> None:
        """publish a text note to relays

        Args:
            text (str): text for nostr note to be published
        """
        # TODO: need regex parsing to handle @
        event = Event(public_key=self.public_key.hex(),
                      content=text,
                      kind=EventKind.TEXT_NOTE)
        self.publish_event(event=event)

    def publish_recommended_relay(self) -> None:
        # TODO: need regex parsing to handle @
        raise NotImplementedError()

    def publish_deletion(self, event_id: str, reason: str) -> None:
        """delete a single event by id

        Args:
            event_id (str): event id/hash
            reason (str): a reason for deletion provided by the user
        """
        event = Event(public_key=self.public_key.hex(),
                      kind=EventKind.DELETE,
                      content=reason,
                      tags=[['e', event_id]])
        self.publish_event(event=event)

    def publish_reaction(self) -> None:
        raise NotImplementedError()

    def publish_channel(self) -> None:
        raise NotImplementedError()

    def publish_channel_metadata(self) -> None:
        raise NotImplementedError()

    def publish_channel_message(self) -> None:
        raise NotImplementedError()

    def publish_channel_hide_message(self) -> None:
        raise NotImplementedError()

    def publish_channel_mute_user(self) -> None:
        raise NotImplementedError()

    def publish_channel_metadata(self) -> None:
        raise NotImplementedError()

    def send_encrypted_message(self) -> None:
        warnings.warn('''the current implementation of messages should be used with caution
                      see https://github.com/nostr-protocol/nips/issues/107''')
        raise NotImplementedError()


class TextInputClient(Client):
    '''
    a simple client that can be run as
    ```
    with TextInputClient():
        pass
    '''

    def __enter__(self):
        '''
        using this object in a with statement
        will open connections and run
        '''
        self.relay_manager.open_connections(self.ssl_options)
        self.message_store = {}
        time.sleep(2)
        self.run()
        return self
    
    def _event_handler(self, event_msg):
        event = event_msg.event
        print(f'author: {event.public_key}\n'
              f'event id: {event.id}\n'
              f'url: {event_msg.url}\n'
              f'\t{event.content}')
        self.message_store.update({f'{event_msg.url}:{event.id}': event_msg})

    def run(self):
        cmd = 'start'
        while cmd not in ['exit', 'x', '0']:
            if cmd != 'start':
                self.execute(cmd)
            menu = '''select a command:
                \t0\tE(x)it
                \t1\tpublish note
                \t2\tget last 10 notes by you
                \t3\tget last 10 from hex of author
                \t4\tdelete an event
                \t5\tcheck deletions
                \t6\tget metadata by hex of user
                \t7\tcheck event
                '''
            print(menu)
            cmd = input('see output for choices').lower()
        print('exiting')
    
    def execute(self, cmd):
        if cmd == '1':
            text_note = input(f'Enter a text note:\n')
            print(f'note:\n\n{text_note}')
            response = input('is the note output below correct? y/n').lower()
            if response in ['y', 'yes']:
                self.publish_text_note(text_note)
                print('published.')
            else:
                print('returning to menu')
        elif cmd == '2':
            author = self.public_key.hex()
            self.request_by_custom_filter(
                subscription_id=f'{author}_last10',
                kinds=[EventKind.TEXT_NOTE],
                authors=[author],
                limit=10
                )
            print(self.message_store)
        elif cmd == '3':
            author = input('who?')
            self.request_by_custom_filter(
                subscription_id=f'{author}_last10',
                kinds=[EventKind.TEXT_NOTE],
                authors=[self.public_key.hex()],
                limit=10
                )
            print(self.message_store)
        elif cmd == '4':
            event_id = input('which event id?')
            reason = input('please give a reason')
            self.publish_deletion(event_id=event_id, reason=reason)
        
        elif cmd == '5':
            author = self.public_key.hex()
            self.request_by_custom_filter(
                subscription_id=f'{author}_last10deletes',
                kinds=[EventKind.DELETE],
                authors=[author],
                limit=10
                )
            print(self.message_store)

        elif cmd == '6':
            author = input('who?')
            self.request_by_custom_filter(
                subscription_id=f'{author}_last10metadata',
                kinds=[EventKind.SET_METADATA],
                authors=[author],
                limit=10
                )
            print(self.message_store)

        elif cmd == '7':
            event_id = input('event id to check?')
            self.request_by_custom_filter(
                subscription_id=f'{event_id}_single_event',
                kinds=[EventKind.TEXT_NOTE],
                ids=[event_id],
                limit=10
                )
            print(self.message_store)
        else:
            print('command not found. returning to menu')
