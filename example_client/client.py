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

from nostr.key import PrivateKey, PublicKey
from nostr.relay_manager import RelayManager
from nostr.message_type import ClientMessageType


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
                'wss://nostr-relay.lnmarkets.com'
            ]
        else:
            pass
        
        self.relay_manager = RelayManager()
        for url in relay_urls:
            self.relay_manager.add_relay(url=url)

######################### publish methods #######################
# establishing methods for all possible events outlined here:   #
# https://github.com/nostr-protocol/nips#event-kinds            #
#################################################################

    def publish_metadata(self):
        raise NotImplementedError()
    
    def publish_text_note(self):
        # TODO: need regex parsing to handle @
        raise NotImplementedError()

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
        return self
    def __exit__(self, type, value, traceback):
        self.relay_manager.close_connections()
