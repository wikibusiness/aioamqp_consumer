import asyncio

import aioamqp

from .log import logger


class AMQPMixin:

    _connected = _closed = False
    _transport = _protocol = _channel = None

    def _on_error_callback(self, exc):
        while hasattr(exc, 'code'):
            _exc = getattr(exc, 'code')

            if isinstance(_exc, Exception):
                exc = _exc
            else:
                break

        _code = getattr(exc, 'code', None)
        _message = getattr(exc, 'message', None)

        if _code is not None or _message is not None:
            logger.exception(exc)

    async def _connect(self, url, on_error=None, **kwargs):
        if self._connected:
            return

        assert not self._closed, 'Already closed'
        assert self._transport is None
        assert self._protocol is None
        assert self._channel is None

        if on_error is None:
            on_error = self._on_error_callback

        kwargs['on_error'] = on_error
        kwargs['loop'] = self.loop

        try:
            self._transport, self._protocol = await aioamqp.from_url(
                url,
                **kwargs
            )
        except OSError as exc:
            raise aioamqp.AioamqpException from exc

        _channel = self._protocol.channel()

        self._channel = await asyncio.shield(_channel, loop=self.loop)

        self._connected = True

        logger.debug('Connected amqp')

    async def _disconnect(self):
        if self._transport is not None and self._protocol is not None:
            if self._channel is not None:
                try:
                    _close = self._channel.close()

                    await asyncio.shield(_close, loop=self.loop)

                    logger.debug('Amqp channel is closed')
                except aioamqp.AioamqpException:
                    pass

            try:
                _close = self._protocol.close()

                await asyncio.shield(_close, loop=self.loop)

                self._transport.close()

                logger.debug('Amqp protocol and transport are closed')
            except (aioamqp.AioamqpException, AttributeError):
                # AttributeError tmp hotfix
                pass

        self._transport = self._protocol = self._channel = None
        self._connected = False

    async def _queue_declare(self, **kwargs):
        _queue_declare = self._channel.queue_declare(**kwargs)

        return await asyncio.shield(_queue_declare, loop=self.loop)

    async def _queue_purge(self, *args, **kwargs):
        _queue_purge = self._channel.queue_purge(*args, **kwargs)

        return await asyncio.shield(_queue_purge, loop=self.loop)

    async def _queue_delete(self, *args, **kwargs):
        _queue_delete = self._channel.queue_delete(*args, **kwargs)

        return await asyncio.shield(_queue_delete, loop=self.loop)

    async def _basic_reject(self, *args, **kwargs):
        _basic_reject = self._channel.basic_reject(*args, **kwargs)

        return await asyncio.shield(_basic_reject, loop=self.loop)

    async def _basic_client_ack(self, *args, **kwargs):
        _ack = self._channel.basic_client_ack(*args, **kwargs)

        return await asyncio.shield(_ack, loop=self.loop)

    async def _basic_qos(self, **kwargs):
        _basic_qos = self._channel.basic_qos(**kwargs)

        return await asyncio.shield(_basic_qos, loop=self.loop)

    async def _basic_consume(self, *args, **kwargs):
        _basic_consume = self._channel.basic_consume(*args, **kwargs)

        return await asyncio.shield(_basic_consume, loop=self.loop)

    async def _basic_publish(self, *args, **kwargs):
        _basic_publish = self._channel.basic_publish(*args, **kwargs)

        return await asyncio.shield(_basic_publish, loop=self.loop)

    async def _basic_cancel(self, *args, **kwargs):
        _basic_cancel = self._channel.basic_cancel(*args, **kwargs)

        return await asyncio.shield(_basic_cancel, loop=self.loop)
