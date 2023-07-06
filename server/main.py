from fastapi import FastAPI, Request, HTTPException
from models import STATUS_TO_HANDLER, StatusModel, AlgorithmRun, AlgorithmRunImage
import uuid
import uvicorn
import tiles_router
from fastapi.staticfiles import StaticFiles
from urllib.parse import urljoin
import requests

memory = {}

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(tiles_router.router)


@app.get('/run_algorithm')
async def run_algorithm(request: Request):
    id = str(uuid.uuid4())
    url_base_part = str(request.base_url)
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

    response = requests.post('http://127.0.0.1:12346/run_algorithm', json=data.dict())

    if response.status_code != 200:
        response.raise_for_status

    print(f'Started processing algorithm run with id: {id}')
    memory[id] = {
        'status': 'in_progress',
        'progress': 0
    }

    return data


@app.post('/integrations/algorithm/{id:str}/status/')
async def process_status(id: str, status: StatusModel):
    print(f'{id=}')
    if id not in memory:
        raise HTTPException(400, f'Algorithm run with ID: {id} was not started')
    if memory[id]['status'] in ['error', 'completed']:
        raise HTTPException(400, f'Algorithm run with ID: {id} is already finished with status: {memory[id]["status"]}')
    STATUS_TO_HANDLER[status.status](status, memory[id])


def main():
    import logging
    # uvicorn.run("main:app",
    #             host='0.0.0.0',
    #             port=12345,
    #             reload=True,
    #             log_level="trace"
    #             )

    uvicorn_config = uvicorn.Config(app, host="0.0.0.0", port=12345, log_level="debug")

    logger = logging.getLogger("uvicorn.access")
    logger.propagate = False
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

    uvicorn.Server(uvicorn_config).run()


if __name__ == '__main__':
    main()
