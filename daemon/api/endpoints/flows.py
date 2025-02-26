from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException

from ... import Runtime400Exception
from ..dependencies import FlowDepends
from ...models import DaemonID, ContainerItem, ContainerStoreStatus, FlowModel
from ...stores import flow_store as store

router = APIRouter(prefix='/flows', tags=['flows'])


@router.get(
    path='', summary='Get all alive Flows\' status', response_model=ContainerStoreStatus
)
async def _get_items():
    return store.status


@router.get(path='/arguments', summary='Get all accepted arguments of a Flow')
async def _fetch_flow_params():
    return FlowModel.schema()['properties']


@router.post(
    path='',
    summary='Create a Flow from a YAML config',
    status_code=201,
    response_model=DaemonID,
)
async def _create(flow: FlowDepends = Depends(FlowDepends)):
    try:
        return await store.add(
            id=flow.id,
            workspace_id=flow.workspace_id,
            params=flow.params,
            ports=flow.ports,
            envs=flow.envs,
            device_requests=flow.device_requests,
        )
    except Exception as ex:
        raise Runtime400Exception from ex


@router.put(
    path='/rolling_update/{id}',
    summary='Trigger a rolling_update operation on the Flow object',
)
async def _rolling_update(
    id: DaemonID,
    pod_name: str,
    dump_path: Optional[str] = None,
    uses_with: Optional[Dict[str, Any]] = None,
):
    try:
        if dump_path is not None:
            if uses_with is not None:
                uses_with['dump_path'] = dump_path
            else:
                uses_with = {'dump_path': dump_path}

        return await store.rolling_update(id=id, pod_name=pod_name, uses_with=uses_with)
    except Exception as ex:
        raise Runtime400Exception from ex


@router.put(
    path='/scale/{id}',
    summary='Trigger a scale operation on the Flow object',
)
async def _scale(id: DaemonID, pod_name: str, replicas: int):
    try:
        return await store.scale(id=id, pod_name=pod_name, replicas=replicas)
    except Exception as ex:
        raise Runtime400Exception from ex


# order matters! this must be put in front of del {id}
#  https://fastapi.tiangolo.com/tutorial/path-params/?h=+path#order-matters
@router.delete(
    path='',
    summary='Terminate all running Flows',
)
async def _clear_all():
    await store.clear()


@router.delete(
    path='/{id}',
    summary='Terminate a running Flow',
    description='Terminate a running Flow and release its resources',
)
async def _delete(id: DaemonID):
    try:
        await store.delete(id=id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f'{id} not found in {store!r}')


@router.get(
    path='/{id}',
    summary='Get the status of a running Flow',
    response_model=ContainerItem,
)
async def _status(id: DaemonID):
    try:
        return store[id]
    except KeyError:
        raise HTTPException(status_code=404, detail=f'{id} not found in flow store')
