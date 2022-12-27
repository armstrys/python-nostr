# python-nostr client
Started this as a fun learning exercise - I am not proficient at code development and this is very much work in progress. I find how easy it is to develop on nostr totally fascinating. 

`client.py` has two classes in it:
 - a base `Client` class that
    - collects and simplifies many of the key features from `python-nostr`
    - allows a user to invoke a client connection and run operations within a `with` statement
 - and a `TextInputClient` class that shows an example of a super bare bones text input client which is most simply invoked by simply calling:
```
with TextInputClient() as client:
    pass
```
