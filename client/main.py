from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
import requests
import argparse
import uvicorn
import random
import time
import os
from pathlib import Path
from math import ceil

app = FastAPI()


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


class StatusModel(BaseModel):
    status: str
    progress: int | None
    error: str | None
    result: Dict[str, Any] | None


def process_image(algorithm_run: AlgorithmRun):
    '''
    This example will download tiles into directory 'tiles', from image downscaled 16 times notifiying in meantime
    CC.AI about progress, after that it will randomly send error ending algorithm run or send
    further progress updates and result at the end
    '''
    try:
        # Assure that folder exists, if not create
        folder_path = Path('./tiles')
        if not folder_path.exists():
            os.mkdir(folder_path)

        times_downscaled = 4
        # Level numbers start at 0
        level = algorithm_run.image.levels - times_downscaled - 1

        # Moving one level down corresponds to downscaling image 2 times
        tiles_x = ceil((algorithm_run.image.width // (2 ** times_downscaled)) /
                       algorithm_run.image.tile_size)
        tiles_y = ceil((algorithm_run.image.height // (2 ** times_downscaled)) /
                       algorithm_run.image.tile_size)

        for y in range(tiles_y):
            for x in range(tiles_x):
                tile_url = algorithm_run.image.tiles_url.format(
                    level=level,
                    x=x,
                    y=y
                )
                response = requests.get(tile_url)
                response.raise_for_status()
                with open(folder_path.joinpath(f'tile_{y}_{x}.jpeg'), 'wb') as tile_file:
                    tile_file.write(response.content)

            # Downloading tiles will take 30% of whole algorithm run time
            # We notify CC.AI about progress after each downloaded row
            response = requests.post(algorithm_run.return_url, data=StatusModel(
                status='in_progress',
                progress=round(((y + 1) / tiles_y) * 30)
            ).json())
            response.raise_for_status()

        # We can also notify about error that occured while running algorithm
        if random.randint(0, 100) < 50:
            response = requests.post(algorithm_run.return_url, data=StatusModel(
                status='error',
                error='Random error occured'
            ).json())
            response.raise_for_status()
            return

        # Notify CC.AI about remaining progress in running algorithm
        for i in range(4, 11):
            response = requests.post(algorithm_run.return_url, data=StatusModel(
                status='in_progress',
                progress=i * 10
            ).json())

            response.raise_for_status()

        # Notify CC.AI that algorithm run completed successfully
        response = requests.post(algorithm_run.return_url, data=StatusModel(
                status='completed',
                result={
                    'regions_of_interest': [
                        {
                            # We want result to be in original image dimensions
                            # even if it is processed downscaled
                            'x': algorithm_run.image.width // 2,
                            'y': algorithm_run.image.height // 2,
                            'w': 100,
                            'h': 100,
                            'label': 'Label 1',
                            'score': 0.97
                        }
                    ]
                }
            ).json())
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"HTTP Error: {e}\nMessage: {response.content.decode('utf-8')}")


@app.post('/run_algorithm')
async def run_algorithm(algorithm_run: AlgorithmRun, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_image, algorithm_run)

    # By default response will have status code 200
    # so CC.AI will know that TPA will process request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port',
        help='Port to run this server',
        default=12346,
        type=int
    )

    args = parser.parse_args()
    uvicorn.run("main:app",
                host='0.0.0.0',
                port=args.port)


if __name__ == '__main__':
    main()
