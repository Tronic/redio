import pkg_resources

from redio import commands, conn, conv, exc, highlevel, pubsub, protocol
from redio.highlevel import Redis

__version__ = pkg_resources.require(__name__)[0].version

del pkg_resources
