"""Runner network boundary: no remote connections; opt-in fixed loopback Bolt."""
from contextlib import contextmanager
import socket
from unittest.mock import patch


@contextmanager
def network_scope(neo4j=False):
    connect,connect_ex=socket.socket.connect,socket.socket.connect_ex
    def allowed(address):
        return neo4j and isinstance(address,tuple) and address[:2]==('127.0.0.1',17687)
    def guarded(sock,address):
        if not allowed(address): raise RuntimeError('remote network prohibited by experiment runner')
        return connect(sock,address)
    def guarded_ex(sock,address):
        if not allowed(address): raise RuntimeError('remote network prohibited by experiment runner')
        return connect_ex(sock,address)
    with patch.object(socket.socket,'connect',guarded),patch.object(socket.socket,'connect_ex',guarded_ex):
        yield
