from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any
from urllib.parse import urljoin
import requests
import argparse
import uvicorn
import time

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
    time.sleep(0.5) # Required when using test-server to give it time to start
    try:
        for i in range(10):
            tile_url = algorithm_run.image.tiles_url.format(
                level=algorithm_run.image.levels - 1,
                x=0,
                y=i
            )
            response = requests.get(tile_url, timeout=10)
            response.raise_for_status()

        response = requests.post(algorithm_run.return_url, data=StatusModel(
            status='in_progress',
            progress=10
        ).json())
        response.raise_for_status()

        for i in range(2, 11):
            response = requests.post(algorithm_run.return_url, data=StatusModel(
                status='in_progress',
                progress=i * 10
            ).json())

            response.raise_for_status()
            time.sleep(1)

        response = requests.post(algorithm_run.return_url, data=StatusModel(
                status='completed',
                result={
                    'regions_of_interest': [
                        {
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
    except requests.exceptions.ConnectionError as e:
        if 'Connection aborted' in str(e):
            return
        print(str(e))


@app.post('/run_algorithm')
async def run_algorithm(algorithm_run: AlgorithmRun, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_image, algorithm_run)
    return 'Ok'


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
