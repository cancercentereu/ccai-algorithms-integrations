#!/usr/bin/env python
#
# deepzoom_server - Example web application for serving whole-slide images
#
# Copyright (c) 2010-2015 Carnegie Mellon University
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of version 2.1 of the GNU Lesser General Public License
# as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from io import BytesIO
import os
import re
from unicodedata import normalize

if os.name == 'nt':
    _dll_path = os.getenv('OPENSLIDE_PATH')
    if _dll_path is not None:
        if hasattr(os, 'add_dll_directory'):
            # Python >= 3.8
            with os.add_dll_directory(_dll_path):
                import openslide
        else:
            # Python < 3.8
            _orig_path = os.environ.get('PATH', '')
            os.environ['PATH'] = _orig_path + ';' + _dll_path
            import openslide

            os.environ['PATH'] = _orig_path
else:
    import openslide

from openslide import ImageSlide, open_slide
from openslide.deepzoom import DeepZoomGenerator

SLIDE_NAME = 'slide'

from fastapi import APIRouter, HTTPException, Request, Response
import sys

class Holder:
    pass


def slugify(text):
    text = normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()
    return re.sub('[^a-z0-9]+', '-', text)


def __init_slide_data(config=None, config_file=None):
    slide_data = Holder()
    config = {'DEEPZOOM_SLIDE': sys.argv[1]}
    config.update({
        'DEEPZOOM_FORMAT': 'jpeg',
        'DEEPZOOM_TILE_SIZE': 512,
        'DEEPZOOM_OVERLAP': 0,
        'DEEPZOOM_LIMIT_BOUNDS': True,
        'DEEPZOOM_TILE_QUALITY': 75,
    })
    # Open slide
    slidefile = config['DEEPZOOM_SLIDE']
    if slidefile is None:
        raise ValueError('No slide file specified')
    config_map = {
        'DEEPZOOM_TILE_SIZE': 'tile_size',
        'DEEPZOOM_OVERLAP': 'overlap',
        'DEEPZOOM_LIMIT_BOUNDS': 'limit_bounds',
    }
    slide_data.config = config
    opts = {v: config[k] for k, v in config_map.items()}
    slide = open_slide(slidefile)
    slide_data.slides = {SLIDE_NAME: DeepZoomGenerator(slide, **opts)}
    slide_data.associated_images = []
    slide_data.slide_properties = slide.properties
    slide_data.level_count = slide_data.slides[SLIDE_NAME].level_count
    slide_data.width = slide_data.slides[SLIDE_NAME].level_dimensions[-1][0]
    slide_data.height = slide_data.slides[SLIDE_NAME].level_dimensions[-1][1]
    slide_data.tile_size = slide_data.config['DEEPZOOM_TILE_SIZE']
    slide_data.objective_magnification = float(slide_data.slide_properties['openslide.objective-power'])
    slide_data.microns_per_pixel = (float(slide_data.slide_properties['openslide.mpp-x']) + float(slide_data.slide_properties['openslide.mpp-y'])) / 2

    for name, image in slide.associated_images.items():
        slide_data.associated_images.append(name)
        slug = slugify(name)
        slide_data.slides[slug] = DeepZoomGenerator(ImageSlide(image), **opts)
    try:
        mpp_x = slide.properties[openslide.PROPERTY_NAME_MPP_X]
        mpp_y = slide.properties[openslide.PROPERTY_NAME_MPP_Y]
        slide_data.slide_mpp = (float(mpp_x) + float(mpp_y)) / 2
    except (KeyError, ValueError):
        slide_data.slide_mpp = 0
    return slide_data


slide_data = __init_slide_data()

router = APIRouter()
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")


@router.get('/')
def index(request: Request):
    slide_url = router.url_path_for('dzi', slug=SLIDE_NAME)
    associated_urls = {
        name: router.url_path_for('dzi', slug=slugify(name))
        for name in slide_data.associated_images
    }

    return templates.TemplateResponse(
        "slide-multipane.html",
        {
            "request": request,
            "slide_url": slide_url,
            "associated": associated_urls,
            "properties": slide_data.slide_properties,
            "slide_mpp": slide_data.slide_mpp,
        },
    )


@router.get('/{slug:str}.dzi')
def dzi(slug: str):
    format = slide_data.config['DEEPZOOM_FORMAT']
    try:
        resp = Response(content=slide_data.slides[slug].get_dzi(format), media_type='application/xml')
        return resp
    except KeyError:
        # Unknown slug
        raise HTTPException(404)


@router.get('/{slug:str}_files/{level:str}/{x:str}_{y:str}.{format:str}')
def tile(slug: str, level: int, col: int, row: int, format: str):
    level = int(level)
    col = int(col)
    row = int(row)
    format = format.lower()
    if format != 'jpeg' and format != 'png':
        # Not supported by Deep Zoom
        raise HTTPException(404)
    try:
        tile = slide_data.slides[slug].get_tile(level, (col, row))
    except KeyError:
        # Unknown slug
        raise HTTPException(404)
    except ValueError:
        # Invalid level or coordinates
        raise HTTPException(404)
    buf = BytesIO()
    tile.save(buf, format, quality=slide_data.config['DEEPZOOM_TILE_QUALITY'])
    resp = Response(content=buf.getvalue(), media_type=f"image/{format}")
    return resp



