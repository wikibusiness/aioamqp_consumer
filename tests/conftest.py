import asyncio
import atexit
import gc
import socket
import time
import uuid

import pytest
from docker import from_env as docker_from_env

from aioamqp_consumer import Producer

asyncio.set_event_loop(None)


def unused_port():
    """Return a port that is unused on the current host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture
def event_loop(request):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    yield loop

    if not loop._closed:
        loop.call_soon(loop.stop)
        loop.run_forever()
        loop.close()

    gc.collect()
    asyncio.set_event_loop(None)


@pytest.fixture
def loop(event_loop):
    return event_loop


@pytest.fixture(scope='session')
def session_id():
    '''Unique session identifier, random string.'''
    return str(uuid.uuid4())


@pytest.fixture(scope='session')
def docker():
    client = docker_from_env(version='auto')
    return client


def pytest_collection_modifyitems(items):
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


def pytest_addoption(parser):
    parser.addoption("--rabbit_tag", action="append", default=[],
                     help=("Rabbitmq server versions. "
                           "May be used several times. "
                           "3.6.11-alpine by default"))
    parser.addoption("--local-docker", action="store_true", default=False,
                     help="Use 0.0.0.0 as docker host, useful for MacOs X")


def pytest_generate_tests(metafunc):
    if 'rabbit_tag' in metafunc.fixturenames:
        tags = set(metafunc.config.option.rabbit_tag)
        if not tags:
            tags = ['3.6.11-alpine']
        else:
            tags = list(tags)
        metafunc.parametrize("rabbit_tag", tags, scope='session')


def probe(container):
    delay = 0.001
    for i in range(20):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((container['host'], container['port']))
            break
        except OSError:
            time.sleep(delay)
            delay = min(delay*2, 1)
        finally:
            s.close()
    else:
        pytest.fail("Cannot start rabbitmq server")


@pytest.fixture(scope='session')
def rabbit_container(docker, session_id, rabbit_tag, request):
    image = 'rabbitmq:{}'.format(rabbit_tag)

    if request.config.option.local_docker:
        rabbit_port = unused_port()
    else:
        rabbit_port = None

    container = docker.containers.run(
        image, detach=True,
        name='rabbitmq-'+session_id,
        ports={'5672/tcp': rabbit_port})

    def defer():
        container.kill(signal=9)
        container.remove(force=True)

    atexit.register(defer)

    if request.config.option.local_docker:
        host = '0.0.0.0'
    else:
        inspection = docker.api.inspect_container(container.id)
        host = inspection['NetworkSettings']['IPAddress']

    ret = {'container': container,
           'host': host,
           'port': 5672,
           'login': 'guest',
           'password': 'guest'}
    probe(ret)
    yield ret


@pytest.fixture
def amqp_url(rabbit_container):
    return 'amqp://{}:{}@{}:{}//'.format(rabbit_container['login'],
                                         rabbit_container['password'],
                                         rabbit_container['host'],
                                         rabbit_container['port'])


@pytest.fixture
def amqp_queue_name():
    return 'test'


@pytest.fixture
def producer(loop, amqp_url, amqp_queue_name):
    producer = Producer(amqp_url, loop=loop)

    loop.run_until_complete(producer.queue_delete(amqp_queue_name))

    yield producer

    producer.close()
    loop.run_until_complete(producer.wait_closed())
