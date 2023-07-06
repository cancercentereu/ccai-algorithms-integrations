from fastapi import FastAPI, Request, HTTPException
from models import STATUS_TO_HANDLER, StatusModel, AlgorithmRun, AlgorithmRunImage
import uuid
import uvicorn
import tiles_router
from fastapi.staticfiles import StaticFiles
from urllib.parse import urljoin

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
    memory[id] = {
        'status': 'in_progress',
        'progress': 0
    }

    return (
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


@app.post('/integrations/algorithm/{id:str}/status/')
def process_status(id: str, status: StatusModel):
    if id not in memory:
        raise HTTPException(400, f'Algorithm run with ID: {id} was not started')
    if memory[id]['status'] in ['error', 'completed']:
        raise HTTPException(400, f'Algorithm run with ID: {id} is already finished with status: {memory[id]["status"]}')
    STATUS_TO_HANDLER[status.status](status, memory[id])


def main():
    uvicorn.run("main:app",
                host='0.0.0.0',
                port=12345,
                reload=True,
                )


if __name__ == '__main__':
    main()
