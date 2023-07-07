from fastapi import FastAPI, HTTPException, BackgroundTasks
from models import STATUS_TO_HANDLER, StatusModel, AlgorithmRun, AlgorithmRunImage
from fastapi.staticfiles import StaticFiles
from urllib.parse import urljoin
from dependencies import arguments
import os
import uuid
import uvicorn
import requests
import tiles_router
import asyncio


class BackgroundRunner:
    async def initialize_algorithm_run(self):
        await asyncio.sleep(0.5)
        args = arguments()
        id = str(uuid.uuid4())
        url_base_part = f'{args.host_url}:{args.port}'
        url_tiles_part = tiles_router.router.url_path_for('tile', slug=tiles_router.SLIDE_NAME,
                                                          level='{level}', x='{x}', y='{y}',
                                                          format='jpeg')
        return_url = urljoin(url_base_part, app.url_path_for('process_status', id=id))
        data = (
            AlgorithmRun(
                image=AlgorithmRunImage(
                    tiles_url=urljoin(url_base_part, url_tiles_part),
                    levels=tiles_router.slide_data.level_count,
                    width=tiles_router.slide_data.width,
                    height=tiles_router.slide_data.height,
                    tile_size=tiles_router.slide_data.tile_size,
                    objective_magnification=tiles_router.slide_data.objective_magnification,
                    microns_per_pixel=tiles_router.slide_data.microns_per_pixel
                ),
                return_url=return_url,
                id=id
            )
        )

        headers = {}

        if args.auth is not None:
            headers['Authorization'] = args.auth

        response = requests.post(args.tpa_url, json=data.dict())
        response.raise_for_status()

        print(f'Started processing algorithm run with id: {id}')
        memory[id] = {
            'status': 'in_progress',
            'progress': 0
        }


async def kill_server():
    await asyncio.sleep(0.5)
    os.kill(os.getpid(), 9)

memory = {}
runner = BackgroundRunner()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(tiles_router.router)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(runner.initialize_algorithm_run())


@app.post('/integrations/algorithm/{id:str}/status/')
async def process_status(id: str, status: StatusModel, background_tasks: BackgroundTasks):
    try:
        if id not in memory:
            raise HTTPException(400, f'Algorithm run with ID: {id} was not started')
        if memory[id]['status'] in ['error', 'completed']:
            raise HTTPException(400, f'Algorithm run with ID: {id} is already\
                finished with status: {memory[id]["status"]}')
        should_kill = STATUS_TO_HANDLER[status.status](status, memory[id])
        if should_kill:
            background_tasks.add_task(kill_server)
    except HTTPException as e:
        print(e)
        raise e


def main():
    args = arguments()
    uvicorn.run(
        "main:app",
        host='0.0.0.0',
        port=args.port,
    )


if __name__ == '__main__':
    main()
