import asyncio

from .mixins import AMQPMixin


class Producer(AMQPMixin):

    def __init__(
        self,
        amqp_url,
        *,
        amqp_kwargs=None,
        loop=None
    ):
        if amqp_kwargs is None:
            amqp_kwargs = {}

        if loop is None:
            loop = asyncio.get_event_loop()

        self.loop = loop

        self.amqp_url = amqp_url

        self.amqp_kwargs = amqp_kwargs

        self._connect_lock = asyncio.Lock(loop=self.loop)

        self._ensure_queue_lock = asyncio.Lock(loop=self.loop)

        self._known_queues = set()

    async def _ensure_queue(self, queue_name, *, queue_kwargs):
        async with self._ensure_queue_lock:
            if queue_name in self._known_queues:
                return

            await self.queue_declare(
                queue_name,
                queue_kwargs=queue_kwargs,
            )

            self._known_queues.add(queue_name)

    async def _connect(self):
        async with self._connect_lock:
            if not self._connected:
                await super()._connect(self.amqp_url, **self.amqp_kwargs)

    async def queue_declare(self, queue_name, *, queue_kwargs=None):
        if queue_kwargs is None:
            queue_kwargs = {}

        try:
            await self._connect()

            result = await self._queue_declare(
                queue_name=queue_name,
                **queue_kwargs
            )
            return result
        except:  # noqa
            await self._disconnect()
            raise

    async def publish(
        self,
        payload,

        queue_name,
        exchange_name='',

        properties=None,
        mandatory=True,
        immediate=False,
        *,
        queue_kwargs=None
    ):
        if queue_kwargs is None:
            queue_kwargs = {}

        assert isinstance(payload, bytes)

        try:
            assert not self._closed, 'Cannot publish while closed'

            await self._connect()

            await self._ensure_queue(
                queue_name,
                queue_kwargs=queue_kwargs,
            )

            result = await self._basic_publish(
                payload,
                exchange_name=exchange_name,
                routing_key=queue_name,
                properties=properties,
                mandatory=mandatory,
                immediate=immediate,
            )
            return result
        except:  # noqa
            await self._disconnect()
            raise

    async def queue_purge(self, queue_name, **kwargs):
        try:
            assert not self._closed, 'Cannot purge while closed'

            await self._connect()

            await self._queue_purge(queue_name, **kwargs)
        except:  # noqa
            await self._disconnect()
            raise

    async def queue_delete(self, queue_name, **kwargs):
        try:
            assert not self._closed, 'Cannot delete while closed'

            await self._connect()

            await self._queue_delete(queue_name, **kwargs)
        except:  # noqa
            await self._disconnect()
            raise

    async def _disconnect(self):
        self._known_queues = set()

        await super()._disconnect()

    def close(self):
        self._closed = True

    async def wait_closed(self):
        assert self._closed, 'Must be closed first'

        await self._disconnect()

    async def __aenter__(self):  # noqa
        return self

    async def __aexit__(self, *exc_info):  # noqa
        self.close()
        await self.wait_closed()
