import atexit
import asyncio
import socket
import time
import uuid

import pytest
from aiohttp.test_utils import unused_port
from docker import from_env as docker_from_env

from aioamqp_consumer import Producer


@pytest.fixture
def loop(request):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    loop.set_debug(True)

    request.addfinalizer(lambda: asyncio.set_event_loop(None))

    yield loop

    loop.call_soon(loop.stop)
    loop.run_forever()
    loop.close()


@pytest.mark.tryfirst
def pytest_pycollect_makeitem(collector, name, obj):
    if collector.funcnamefilter(name):
        item = pytest.Function(name, parent=collector)

        if 'run_loop' in item.keywords:
            return list(collector._genfunctions(name, obj))


@pytest.mark.tryfirst
def pytest_pyfunc_call(pyfuncitem):
    if 'run_loop' in pyfuncitem.keywords:
        funcargs = pyfuncitem.funcargs

        loop = funcargs['loop']

        testargs = {
            arg: funcargs[arg]
            for arg in pyfuncitem._fixtureinfo.argnames
        }

        assert asyncio.iscoroutinefunction(pyfuncitem.obj)

        loop.run_until_complete(pyfuncitem.obj(**testargs))

        return True


@pytest.fixture(scope='session')
def session_id():
    '''Unique session identifier, random string.'''
    return str(uuid.uuid4())


@pytest.fixture(scope='session')
def docker():
    client = docker_from_env(version='auto')
    return client


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
