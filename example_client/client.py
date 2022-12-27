"""
a barebones client implementation based on python-nostr

TODO: add new features
 - switch accounts
 - change relays with Client.connect and disconnect methods
 - figure out how to reset message pool or better deal with old requests?
 - regex handling of @ in text
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
                 first_response_only: bool = True):
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
        self.first_response_only = first_response_only
        self.set_account(public_key_hex=public_key_hex,
                          private_key_hex=private_key_hex)
        if relay_urls is None:
            relay_urls = [
                'wss://nostr-2.zebedee.cloud',
                'wss://nostr-relay.lnmarkets.com',
                'wss://relay.damus.io',
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
        for url, connected in self.connection_statuses.items():
            if not connected:
                warnings.warn(
                    f'could not connect to {url}... removing relay.'
                )
                self.relay_manager.remove_relay(url=url)
        assert all(self.connection_statuses.values())
        self._is_connected = True
    
    def disconnect(self) -> None:
        time.sleep(2)
        self.relay_manager.close_connections()
        self._is_connected = False
    
    @property
    def relay_urls(self) -> list:
        return [relay.url for relay in self.relay_manager]
    
    @property
    def connection_statuses(self) -> dict:
        """gets the url and connection statuses of relays

        Returns:
            dict: bool of connection statuses
        """
        statuses = [relay.is_connected for relay in self.relay_manager]
        return dict(zip(self.relay_urls, statuses))

    def set_account(self, public_key_hex: str = None, private_key_hex: str = None) -> None:
        """logic to set public and private keys

        Args:
            public_key_hex (str, optional): if only public key is provided, operations
                that require a signature will fail. Defaults to None.
            private_key_hex (str, optional): _description_. Defaults to None.

        Raises:
            ValueException: if the private key and public key are both provided but
                don't match
        """
        self.private_key = None
        self.public_key = None
        if private_key_hex is None:
            self.private_key = self._request_private_key_hex()
        else:
            self.private_key = PrivateKey.from_hex(private_key_hex)

        if public_key_hex is None:
            self.public_key = self.private_key.public_key
        else:
            self.public_key = PublicKey.from_hex(public_key_hex)
        public_key_hex = self.public_key.hex()
        
        if public_key_hex != self.private_key.public_key.hex():
            self.public_key = PublicKey.from_hex(public_key_hex)
            self.private_key = None
        print(f'logged in as public key\n'
              f'\tbech32: {self.public_key.bech32()}\n'
              f'\thex: {self.public_key.hex()}')
    
    def _request_private_key_hex(self) -> str:
        """method to request private key. this method should be overwritten
        when building out a UI

        Returns:
            PrivateKey: the new private_key object for the client. will also
                be set in place at self.private_key
        """
        self.private_key = PrivateKey()
        return self.private_key
    
    def set_relays(self, relay_urls: list = None):
        was_connected = self._is_connected
        if self._is_connected:
            self.disconnect()
        self.relay_manager = RelayManager(first_response_only=self.first_response_only)
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


################### filter building methods #####################
#  this section is reserved for methods used to build filters   #
#  that can be used in requests to relays. things like get      #
#  all posts from a list of user ids with a limit of x.         #
#                                                               #
#################################################################
# TODO: BUILD methods and a static filter dict


class TextInputClient(Client):
    '''
    a simple client that can be run as
    ```
    with TextInputClient():
        pass
    '''
    ## changing a few key methods that are used in the base class ##

    def __init__(self, *args, **kwargs):
        """adding a message store where we
        can store messages using the _event_handler method
        """
        super().__init__(*args, **kwargs)
        self.message_store = {}

    def __enter__(self):
        super().__enter__()
        self.run()
        return self
    
    def _request_private_key_hex(self) -> PrivateKey:
        """the only requirement of this method is that it
        needs to in some way set the self.private_key
        attribute to an instance of PrivateKey
        """
        user_hex = input('please enter a private key hex')
        if user_hex.strip() == '':
            user_hex = 'x'
        try:
            self.private_key = PrivateKey.from_hex(user_hex)
            print('successfully loaded')
        except:
            print('could not generate private key from input. '
                  'generating a new random key')
            self.private_key = PrivateKey()
            print(f'generated new private key: {self.private_key.hex()}')
        return self.private_key

    def _event_handler(self, event_msg) -> None:
        event = event_msg.event
        print(f'author: {event.public_key}\n'
              f'event id: {event.id}\n'
              f'url: {event_msg.url}\n'
              f'\t{event.content}')
        self.message_store.update({f'{event_msg.url}:{event.id}': event_msg})

    ########## adding a couple methods used to run the app! ###########
    ## these could be replaced by a more complex interface in theory ##

    def run(self) -> None:
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
                \t8\tget recommended server
                \t9\tget contacts
                \t10\tprint relays
                \t11\tadd relay
                '''
            print(menu)
            cmd = input('see output for choices').lower()
        print('exiting')
    
    def execute(self, cmd) -> None:
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
        elif cmd == '8':
            author = input('user to check?')
            self.request_by_custom_filter(
                subscription_id=f'{author}_recommended_server',
                kinds=[EventKind.RECOMMEND_RELAY],
                authors=[author],
                limit=10
                )
            print(self.message_store)
        elif cmd == '9':
            author = input('user to check?')
            self.request_by_custom_filter(
                subscription_id=f'{author}_contacts',
                kinds=[EventKind.CONTACTS],
                authors=[author],
                limit=10
                )
            print(self.message_store)
        elif cmd == '10':
            print(self.relay_urls)
        elif cmd == '11':
            relay_url = input('what is the relay url')
            self.set_relays(self.relay_urls + [relay_url])
            print(f'connection status: {self.connection_statuses}')

        else:
            print('command not found. returning to menu')

relay_list = [
    'wss://nostr.coinos.io',
    'wss://nostr.actn.io',
    'wss://lv01.tater.ninja',
    'wss://nostr.rdfriedl.com',
    'wss://nostr.nymsrelay.com',
    'wss://relay.nostr.pro',
    'wss://relay.cryptocculture.com',
    'wss://nostr-dev.wellorder.net',
    'wss://nostr.radixrat.com',
    'wss://nostr.bongbong.com',
    'wss://nostr.fly.dev',
    'wss://nostr-2.zebedee.cloud',
    'wss://relay.farscapian.com',
    'wss://relay.sendstr.com',
    'wss://relay.oldcity-bitcoiners.info',
    'wss://relay.sovereign-stack.org',
    'wss://nostr.shawnyeager.net',
    'wss://nostr-relay.derekross.me',
    'wss://nostr.supremestack.xyz',
    'wss://nostr.delo.software',
    'wss://relay.r3d.red',
    'wss://nostr.v0l.io',
    'wss://nostrrelay.com',
    'wss://nostr.zerofeerouting.com',
    'wss://relay.nostr.ch',
    'wss://nostr.mwmdev.com',
    'wss://nostr.einundzwanzig.space',
    'wss://no.str.cr',
    'wss://public.nostr.swissrouting.com',
    'wss://nostr.nordlysln.net',
    'wss://nostr.slothy.win',
    'wss://nostr.rocks',
    'wss://nostr-01.bolt.observer',
    'wss://nostr.yael.at',
    'wss://relay.21spirits.io',
    'wss://nostr.cercatrova.me',
    'wss://relay.kronkltd.net',
    'wss://relay.nostropolis.xyz/websocket',
    'wss://nostr-relay.freedomnode.com',
    'wss://nostr.openchain.fr',
    'wss://nostr-relay.digitalmob.ro',
    'wss://nostr-relay.trustbtc.org',
    'wss://nostr.swiss-enigma.ch',
    'wss://nostr.ono.re',
    'wss://nostr.oooxxx.ml',
    'wss://nostr-relay.schnitzel.world',
    'wss://nostr.rewardsbunny.com',
    'wss://nostr.sandwich.farm',
    'wss://relay.nostr.au',
    'wss://nostr.8e23.net',
    'wss://nostr.jiashanlu.synology.me',
    'wss://nostr.mom',
    'wss://nostr.shadownode.org',
    'wss://nostr.satsophone.tk',
    'wss://mule.platanito.org',
    'wss://nostr.orba.ca',
    'wss://nostr.pobblelabs.org',
    'wss://nostr-relay.untethr.me',
    'wss://nostr-verified.wellorder.net',
    'wss://nostr.zaprite.io',
    'wss://relay.minds.com/nostr/v1/ws',
    'wss://expensive-relay.fiatjaf.com',
    'wss://wlvs.space',
    'wss://nostr.semisol.dev',
    'wss://nostr-relay.wlvs.space',
    'wss://nostr.onsats.org',
    'wss://nostr.oxtr.dev',
    'wss://nostr.fmt.wiz.biz',
    'wss://nostr-pub.wellorder.net',
    'wss://satstacker.cloud',
    'wss://relay.damus.io',
    'wss://nostr-relay.lnmarkets.com',
    'wss://nostr-pub.semisol.dev',
    'wss://rsslay.nostr.net',
    'wss://nostr-relay.nonce.academy',
    'wss://relay.minds.io/nostr/v1/ws',
    'wss://nostr.gruntwerk.org',
    'wss://nostr-3.orba.ca',
    'wss://freedom-relay.herokuapp.com/ws',
    'wss://nostr-relay.freeberty.net',
    'wss://nostr-relay-dev.wlvs.space',
    'wss://nostr.unknown.place',
    'wss://nostr.drss.io',
    'wss://nostr.bitcoiner.social',
    'wss://relay.nostr.info',
    'wss://relay.grunch.dev',
    'wss://relay.cynsar.foundation',
    'wss://relay.bitid.nz',
    'wss://relay.nostr.xyz',
    'wss://relay.futohq.com',
    'wss://astral.ninja',
    'wss://nostr.zebedee.cloud',
    'wss://relay.valireum.net',
    'wss://nostr-relay.gkbrk.com',
    'wss://nostr-2.orba.ca',
    'wss://nostr.namek.link',
    'wss://nostr-relay.wolfandcrow.tech',
    'wss://relay.dev.kronkltd.net',
    'wss://nostr2.namek.link',
    'wss://nostr.d11n.net',
    'wss://nostr1.tunnelsats.com',
    'wss://nostr.tunnelsats.com',
    'wss://nostr.leximaster.com',
    'wss://nostr.hugo.md',
    'wss://relay.ryzizub.com',
    'wss://nostr.w3ird.tech',
    'wss://nostr.robotechy.com',
    'wss://relay.stoner.com',
    'wss://relay.nostrmoto.xyz',
    'wss://relay.boring.surf',
    'wss://nostr.mado.io',
    'wss://nostr.corebreach.com',
    'wss://nostr.hyperlingo.com',
    'wss://nostr.ethtozero.fr',
    'wss://relay.nvote.co',
    'wss://jiggytom.ddns.net',
    'wss://nostr.sectiontwo.org',
    'wss://nostr.roundrockbitcoiners.com',
    'wss://nostr.nodeofsven.com',
    'wss://nostr.jimc.me',
    'wss://nostr.utxo.lol',
    'wss://relay.lexingtonbitcoin.org',
    'wss://nostr.mikedilger.com',
    'wss://nostr.f44.dev',
    'wss://relay.nyx.ma',
    'wss://nostr.walletofsatoshi.com',
    'wss://nostr.shmueli.org',
    'wss://wizards.wormrobot.org',
    'wss://nostr.orangepill.dev',
    'wss://paid.no.str.cr',
    'wss://nostr.sovbit.com',
    'wss://nostr.datamagik.com',
    'wss://relay.nostrid.com',
    'wss://nostr1.starbackr.me',
    'wss://relay.nostr.express',
    'wss://sg.qemura.xyz',
    'wss://nostr.formigator.eu',
    'wss://nostr.xpersona.net',
    'wss://relay.n057r.club',
    'wss://nostr.digitalreformation.info',
    'wss://nostr.gromeul.eu',
    'wss://nostr-relay.alekberg.net',
    ]
