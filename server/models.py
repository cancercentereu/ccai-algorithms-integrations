from pydantic import BaseModel
from typing import Dict, Any, Callable
from collections import defaultdict
from fastapi import HTTPException
import os


ALLOWED_STATUSES = [
    'in_progress',
    'error',
    'completed'
]


class StatusModel(BaseModel):
    status: str
    progress: int | None
    error: str | None
    result: Dict[str, Any] | None


class AlgorithmRunImage(BaseModel):
    tiles_url: str
    levels: int
    width: int
    height: int
    tile_size: int
    objective_magnification: float
    microns_per_pixel: float


class AlgorithmRun(BaseModel):
    image: AlgorithmRunImage
    return_url: str
    id: str


def handle_completed(status: StatusModel, memory):
    if status.result is None:
        raise HTTPException(400, 'Missing field result')
    memory['status'] = 'completed'
    print(f'Algorithm run completed with result: {status.result}')


def handle_in_progress(status: StatusModel, memory):
    if status.progress is None:
        raise HTTPException(400, 'Missing field progress')
    memory['progress'] = status.progress
    print(f'Algorithm run progress: {status.progress}')


def handle_error(status: StatusModel, memory):
    if status.error is None:
        raise HTTPException(400, 'Missing field error')
    memory['status'] = 'error'
    print(f'Algorithm run failed with error: {status.error}')


def handle_wrong_status(status: StatusModel, memory):
    raise HTTPException(400, f'Invalid status {status.status}')


STATUS_TO_HANDLER: defaultdict[str, Callable[[StatusModel, dict], None]] = defaultdict(
    lambda: handle_wrong_status,
    {
        'in_progress': handle_in_progress,
        'error': handle_error,
        'completed': handle_completed
    }
)
