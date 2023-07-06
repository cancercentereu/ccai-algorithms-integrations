import argparse
from functools import lru_cache


@lru_cache
def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--image_path',
        help='Path to image whose tiles will be served',
        required=True,
        type=str
    )

    parser.add_argument(
        '--tpa_url',
        help='Url to TPA algorithm server endpoint that initializes algorithm run',
        default='http://127.0.0.1:12346/run_algorithm',
        type=str
    )

    parser.add_argument(
        '--auth',
        help='Authorization value that will be sent in Authorization header',
        default=None,
        type=str
    )

    parser.add_argument(
        '--port',
        help='Port to run this server',
        default=12345,
        type=int
    )

    parser.add_argument(
        '--host_url',
        help='This server\'s url',
        default=r'http://127.0.0.1',
        type=str
    )

    args = parser.parse_args()
    return args
