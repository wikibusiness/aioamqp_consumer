import pytest
from aioamqp_consumer import Consumer

from tests.conftest import AMQP_QUEUE, AMQP_URL


@pytest.mark.run_loop
async def test_consumer_smoke(producer, loop):
    test_data = [b'test'] * 5

    for data in test_data:
        await producer.publish(data, AMQP_QUEUE)

    test_results = []

    async def task(payload, options):
        test_results.append(payload)

    consumer = Consumer(
        AMQP_URL,
        task,
        AMQP_QUEUE,
        loop=loop,
    )

    await consumer.join()

    consumer.close()
    await consumer.wait_closed()

    assert test_results == test_data
