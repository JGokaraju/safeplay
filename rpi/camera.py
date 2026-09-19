import io

from PIL import Image
from picamera2 import Picamera2

_cam = None


def capture_jpeg(max_side=1024):
    global _cam
    if _cam is None:
        _cam = Picamera2()
        _cam.configure(_cam.create_still_configuration())
        _cam.start()
    img = Image.fromarray(_cam.capture_array()).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()
