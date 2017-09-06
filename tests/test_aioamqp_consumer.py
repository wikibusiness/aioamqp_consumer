from aioamqp_consumer import Consumer


async def test_consumer_smoke(producer, loop, amqp_queue_name, amqp_url):
    test_data = [b'test'] * 5

    for data in test_data:
        await producer.publish(data, amqp_queue_name)

    test_results = []

    async def task(payload, options):
        test_results.append(payload)

    consumer = Consumer(
        amqp_url,
        task,
        amqp_queue_name,
        loop=loop,
    )

    await consumer.join()

    consumer.close()
    await consumer.wait_closed()

    assert test_results == test_data
