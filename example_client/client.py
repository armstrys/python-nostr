"""
a barebones client implementation based on python-nostr
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

from nostr.key import PrivateKey, PublicKey
from nostr.relay_manager import RelayManager
from nostr.message_type import ClientMessageType
from nostr.event import Event


class Client:

    def __init__(self, public_key_hex: str = None, private_key_hex: str = None,
             relay_urls: list = None):
        """A basic framework for common operations that a nostr client will
        need to execute.

        Args:
            public_key_hex (str, optional): public key to initiate client
            private_key_hex (str, optional): private key to log in with public key.
                Defaults to None, in which case client is effectively read only
            relay_urls (list, optional): provide a list of relay urls.
                Defaults to None, in which case a default list will be used.
        """
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
        
        if relay_urls is None:
            relay_urls = [
                'wss://nostr-2.zebedee.cloud',
                'wss://nostr.zebedee.cloud',
                'wss://relay.damus.io'
            ]
        else:
            pass
        
        self.relay_manager = RelayManager()
        for url in relay_urls:
            self.relay_manager.add_relay(url=url)
    
    @staticmethod
    def event_to_message(event_type: ClientMessageType, event: Event):
        return json.dumps([event_type, event])

    def publish_to_relay(self, message: str):
        self.relay_manager.publish_message(message)

######################### publish methods #######################
# establishing methods for all possible events outlined here:   #
# https://github.com/nostr-protocol/nips#event-kinds            #
#################################################################

    def publish_metadata(self):
        raise NotImplementedError()
    
    def publish_text_note(self, text):
        # TODO: need regex parsing to handle @
        event = Event(self.public_key.hex(), text)
        event.sign(self.private_key.hex())
        message = self.event_to_message(event_type=ClientMessageType.EVENT,
                                        event=event.to_json_object())
        self.publish_to_relay(message)

    def publish_recommended_relay(self):
        # TODO: need regex parsing to handle @
        raise NotImplementedError()

    def publish_deletion(self):
        raise NotImplementedError()

    def publish_reaction(self):
        raise NotImplementedError()

    def publish_channel(self):
        raise NotImplementedError()

    def publish_channel_metadata(self):
        raise NotImplementedError()

    def publish_channel_message(self):
        raise NotImplementedError()

    def publish_channel_hide_message(self):
        raise NotImplementedError()

    def publish_channel_mute_user(self):
        raise NotImplementedError()

    def publish_channel_metadata(self):
        raise NotImplementedError()

    def send_encrypted_message(self):
        warnings.warn('''the current implementation of messages should be used with caution
                      see https://github.com/nostr-protocol/nips/issues/107''')
        raise NotImplementedError()


class ConnectedClient(Client):
    def __init__(self, ssl_options, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ssl_options = ssl_options
    def __enter__(self):
        self.relay_manager.open_connections(self.ssl_options)
        time.sleep(2)
        return self
    def __exit__(self, type, value, traceback):
        time.sleep(2)
        self.relay_manager.close_connections()


class TextInputClient(ConnectedClient):
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
        time.sleep(2)
        self.run()
        return self

    def run(self):
        cmd = 'start'
        while cmd not in ['exit', 'x', '0']:
            if cmd != 'start':
                self.execute(cmd)
            print(
                '''select a command:
                \t0\tE(x)it
                \t1\tpublish note
                '''
            )
            cmd = input().lower()
        print('exiting')
    
    def execute(self, cmd):
        if cmd == '1':
            print(f'Enter a text note:\n')
            text_note = input()
            print(f'is this note correct?\n\n{text_note}')
            response = input().lower()
            if response in ['y', 'yes']:
                self.publish_text_note(text_note)
                print('published.')
            else:
                print('returning to menu')
        else:
            print('command not found. returning to menu')
