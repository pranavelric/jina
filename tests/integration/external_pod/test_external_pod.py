import pytest

from jina.peapods.pods.factory import PodFactory
from jina.peapods import Pea
from jina.parsers import set_pod_parser, set_pea_parser

from jina import Flow, Executor, requests, Document, DocumentArray
from jina.helper import random_port


def validate_response(resp, expected_docs=50):
    assert len(resp.data.docs) == expected_docs
    for doc in resp.data.docs:
        assert 'external_real' in doc.tags['name']


@pytest.fixture(scope='function')
def input_docs():
    return DocumentArray([Document() for _ in range(50)])


@pytest.fixture
def num_replicas(request):
    return request.param


@pytest.fixture
def num_shards(request):
    return request.param


@pytest.fixture(scope='function')
def external_pod_args(num_replicas, num_shards):
    args = [
        '--uses',
        'MyExternalExecutor',
        '--name',
        'external_real',
        '--port-in',
        str(random_port()),
        '--host-in',
        '0.0.0.0',
        '--shards',
        str(num_shards),
        '--replicas',
        str(num_replicas),
        '--polling',
        'all',
    ]
    return set_pod_parser().parse_args(args)


@pytest.fixture
def external_pod(external_pod_args):
    return PodFactory.build_pod(external_pod_args)


class MyExternalExecutor(Executor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @requests
    def foo(self, docs, *args, **kwargs):
        for doc in docs:
            doc.tags['name'] = self.runtime_args.name


@pytest.mark.parametrize('num_replicas', [1, 2], indirect=True)
@pytest.mark.parametrize('num_shards', [1, 2], indirect=True)
def test_flow_with_external_pod(
    external_pod, external_pod_args, input_docs, num_replicas, num_shards
):
    with external_pod:
        external_args = vars(external_pod_args)
        del external_args['name']
        del external_args['external']
        del external_args['pod_role']
        del external_args['dynamic_routing']
        flow = Flow().add(
            **external_args,
            name='external_fake',
            external=True,
        )
        with flow:
            resp = flow.index(inputs=input_docs, return_results=True)

        # expect 50 reduced Documents in total after sharding
        validate_response(resp[0], 50)


@pytest.fixture(scope='function')
def external_executor_args():
    args = [
        '--uses',
        'MyExternalExecutor',
        '--name',
        'external_real',
        '--port-in',
        str(random_port()),
        '--host-in',
        '0.0.0.0',
        '--socket-in',
        'ROUTER_BIND',
        '--dynamic-routing-out',
    ]
    return set_pea_parser().parse_args(args)


@pytest.fixture
def external_executor(external_executor_args):
    return Pea(external_executor_args)


def test_flow_with_external_executor(
    external_executor, external_executor_args, input_docs
):
    with external_executor:
        external_args = vars(external_executor_args)
        del external_args['name']
        flow = Flow().add(
            **external_args,
            name='external_fake',
            external=True,
        )
        with flow:
            resp = flow.index(inputs=input_docs, return_results=True)
        validate_response(resp[0])


@pytest.mark.parametrize('num_replicas', [2], indirect=True)
@pytest.mark.parametrize('num_shards', [2], indirect=True)
def test_two_flow_with_shared_external_pod(
    external_pod, external_pod_args, input_docs, num_replicas, num_shards
):
    with external_pod:
        external_args = vars(external_pod_args)
        del external_args['name']
        del external_args['external']
        del external_args['pod_role']
        del external_args['dynamic_routing']
        flow1 = Flow().add(
            **external_args,
            name='external_fake',
            external=True,
        )

        flow2 = (
            Flow()
            .add(name='foo')
            .add(
                **external_args,
                name='external_fake',
                external=True,
                needs=['gateway', 'foo'],
            )
        )
        with flow1, flow2:
            results = flow1.index(inputs=input_docs, return_results=True)

            # Reducing applied after shards, expect only 50 docs
            validate_response(results[0], 50)

            # Reducing applied only after shards, not after needs (external pod is immutable), expect 100 docs
            results = flow2.index(inputs=input_docs, return_results=True)
            validate_response(results[0], 50 * 2)


def test_two_flow_with_shared_external_executor(
    external_executor,
    external_executor_args,
    input_docs,
):
    with external_executor:
        external_args = vars(external_executor_args)
        del external_args['name']
        flow1 = Flow().add(
            **external_args,
            name='external_fake',
            external=True,
        )

        flow2 = (
            Flow()
            .add(name='foo')
            .add(
                **external_args,
                name='external_fake',
                external=True,
                needs=['gateway', 'foo'],
            )
        )
        with flow1, flow2:
            results = flow1.index(inputs=input_docs, return_results=True)
            validate_response(results[0])

            results = flow2.index(inputs=input_docs, return_results=True)
            validate_response(results[0], 50 * 2)


@pytest.fixture(scope='function')
def external_pod_shards_1_args(num_replicas, num_shards):
    args = [
        '--uses',
        'MyExternalExecutor',
        '--name',
        'external_real_1',
        '--port-in',
        str(random_port()),
        '--host-in',
        '0.0.0.0',
        '--shards',
        str(num_shards),
        '--replicas',
        str(num_replicas),
        '--polling',
        'all',
    ]
    return set_pod_parser().parse_args(args)


@pytest.fixture
def external_pod_shards_1(external_pod_shards_1_args):
    return PodFactory.build_pod(external_pod_shards_1_args)


@pytest.fixture(scope='function')
def external_pod_shards_2_args(num_replicas, num_shards):
    args = [
        '--uses',
        'MyExternalExecutor',
        '--name',
        'external_real_2',
        '--port-in',
        str(random_port()),
        '--host-in',
        '0.0.0.0',
        '--shards',
        str(num_shards),
        '--replicas',
        str(num_replicas),
        '--polling',
        'all',
    ]
    return set_pod_parser().parse_args(args)


@pytest.fixture
def external_pod_shards_2(external_pod_shards_2_args):
    return PodFactory.build_pod(external_pod_shards_2_args)


@pytest.mark.parametrize('num_replicas', [1, 2], indirect=True)
@pytest.mark.parametrize('num_shards', [1, 2], indirect=True)
def test_flow_with_external_pod_shards(
    external_pod_shards_1,
    external_pod_shards_2,
    external_pod_shards_1_args,
    external_pod_shards_2_args,
    input_docs,
    num_replicas,
    num_shards,
):
    with external_pod_shards_1, external_pod_shards_2:
        external_args_1 = vars(external_pod_shards_1_args)
        external_args_2 = vars(external_pod_shards_2_args)
        del external_args_1['name']
        del external_args_1['external']
        del external_args_1['pod_role']
        del external_args_1['dynamic_routing']
        del external_args_2['name']
        del external_args_2['external']
        del external_args_2['pod_role']
        del external_args_2['dynamic_routing']
        flow = (
            Flow()
            .add(name='executor1')
            .add(
                **external_args_1,
                name='external_fake_1',
                external=True,
                needs=['executor1'],
            )
            .add(
                **external_args_2,
                name='external_fake_2',
                external=True,
                needs=['executor1'],
            )
            .join(needs=['external_fake_1', 'external_fake_2'], port_in=random_port())
        )

        with flow:
            resp = flow.index(inputs=input_docs, return_results=True)

        # Reducing applied on shards and needs, expect 50 docs
        validate_response(resp[0], 50)


@pytest.fixture(scope='function')
def external_pod_pre_shards_args(num_replicas, num_shards):
    args = [
        '--uses',
        'MyExternalExecutor',
        '--name',
        'external_real',
        '--port-in',
        str(random_port()),
        '--host-in',
        '0.0.0.0',
        '--shards',
        str(num_shards),
        '--replicas',
        str(num_replicas),
        '--polling',
        'all',
    ]
    return set_pod_parser().parse_args(args)


@pytest.fixture
def external_pod_pre_shards(external_pod_pre_shards_args):
    return PodFactory.build_pod(external_pod_pre_shards_args)


@pytest.mark.parametrize('num_replicas', [1, 2], indirect=True)
@pytest.mark.parametrize('num_shards', [1, 2], indirect=True)
def test_flow_with_external_pod_pre_shards(
    external_pod_pre_shards,
    external_pod_pre_shards_args,
    input_docs,
    num_replicas,
    num_shards,
):
    with external_pod_pre_shards:
        external_args = vars(external_pod_pre_shards_args)
        del external_args['name']
        del external_args['external']
        del external_args['pod_role']
        del external_args['dynamic_routing']
        flow = (
            Flow()
            .add(
                **external_args,
                name='external_fake',
                external=True,
            )
            .add(
                name='executor1',
                needs=['external_fake'],
            )
            .add(
                name='executor2',
                needs=['external_fake'],
            )
            .join(needs=['executor1', 'executor2'])
        )
        with flow:
            resp = flow.index(inputs=input_docs, return_results=True)

        # Reducing applied on shards and needs, expect 50 docs
        validate_response(resp[0], 50)


@pytest.fixture(scope='function')
def external_pod_join_args(num_replicas, num_shards):
    args = [
        '--uses',
        'MyExternalExecutor',
        '--name',
        'external_real',
        '--port-in',
        str(random_port()),
        '--host-in',
        '0.0.0.0',
        '--pod-role',
        'JOIN',
        '--shards',
        str(num_shards),
        '--replicas',
        str(num_replicas),
        '--polling',
        'all',
    ]
    return set_pod_parser().parse_args(args)


@pytest.fixture
def external_pod_join(external_pod_join_args):
    return PodFactory.build_pod(external_pod_join_args)


@pytest.mark.parametrize('num_replicas', [1, 2], indirect=True)
@pytest.mark.parametrize('num_shards', [1, 2], indirect=True)
def test_flow_with_external_pod_join(
    external_pod_join,
    external_pod_join_args,
    input_docs,
    num_replicas,
    num_shards,
):
    with external_pod_join:
        external_args = vars(external_pod_join_args)
        del external_args['name']
        del external_args['external']
        del external_args['pod_role']
        del external_args['dynamic_routing']
        flow = (
            Flow()
            .add(
                **external_args,
                external=True,
            )
            .add(
                name='executor1',
                needs=['executor0'],
            )
            .add(
                name='executor2',
                needs=['executor0'],
            )
            .join(
                **external_args,
                external=True,
                needs=['executor1', 'executor2'],
            )
        )
        with flow:
            resp = flow.index(inputs=input_docs, return_results=True)

        # Reducing applied only after shards, not after needs (external pod is immutable), expect 100 docs
        validate_response(resp[0], 50 * 2)
