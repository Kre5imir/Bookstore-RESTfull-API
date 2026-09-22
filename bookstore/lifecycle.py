import atexit
import logging

from django.conf import settings

logger = logging.getLogger("bookstore.lifecycle")
_registered = False


def register():
    global _registered
    if _registered:
        return
    _registered = True
    logger.info("Bookstore API starting version=%s", settings.APP_VERSION)
    atexit.register(_shutdown)


def _shutdown():
    logger.info("Bookstore API shutting down version=%s", settings.APP_VERSION)
