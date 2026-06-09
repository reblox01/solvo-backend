from fastapi import APIRouter
import base64
import logging

logger = logging.getLogger("solvo-backend")
from io import BytesIO
from apps.calculator.utils import analyze_image
from schema import ImageData
from PIL import Image

router = APIRouter()

@router.post('')
async def run(data: ImageData):
    image_data = base64.b64decode(data.image.split(',')[1])
    image = Image.open(BytesIO(image_data))
    image.load()  # Force full read into memory so stream position doesn't matter
    responses = analyze_image(image, dict_of_vars=data.dict_of_vars)
    data = []
    for response in responses:
        data.append(response)
        logger.debug("response in route: %s", response)
    
    return {
        "message": "Image Processed",
        "type": "success",
        "data": data,
    }