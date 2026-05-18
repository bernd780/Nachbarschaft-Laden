from PIL import Image
import numpy as np

import os
_DIR = os.path.dirname(os.path.abspath(__file__))
img = Image.open(os.path.join(_DIR, "images", "logo.PNG"))
print("Image size:", img.size)
img.thumbnail((630, 250))
img.save(os.path.join(_DIR, "images", "logo_debug.png"))
print("Preview saved")
