import pickle

from .log import logger


class DeliveryException(Exception):
    pass


class Ack(DeliveryException):
    pass


class Reject(DeliveryException):
    pass


class DeadLetter(DeliveryException):
    pass


class RpcError(Exception):

    content_type = 'application/python-pickle'

    def __init__(self, err):
        self.err = err

    def _dumps(self, err):
        return pickle.dumps(err, protocol=pickle.HIGHEST_PROTOCOL)

    def dumps(self):
        try:
            return self._dumps(self.err)
        except (pickle.PickleError, NotImplementedError) as exc:
            logger.warning(exc, exc_info=exc)

            return self._dumps(exc)

    @classmethod
    def loads(cls, pkl):
        try:
            return cls(pickle.loads(pkl))
        except pickle.PickleError as exc:
            logger.warning(exc, exc_info=exc)

            return cls(exc)
