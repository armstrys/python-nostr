# python-nostr client
Started this as a fun learning exercise - I am not proficient at code development and this is very much work in progress. I find how easy it is to develop on nostr totally fascinating. 

`client.py` has 3 classes in it:
 - a base `Client` class that collects and simplifies many of the key features from `python-nostr`
 - a `ConnectedClient` class that allows a user to invoke a client connection and run operations within a `with` statement
 - and a `TextInputClient` class that shows an example of a super bare bones text input client which is invoked by simply calling
```
with TextInputClient(private_key_hex=pk_hex) as client:
    pass
```