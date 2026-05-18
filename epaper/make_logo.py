import cairosvg
import io
from PIL import Image
import numpy as np

import os
_DIR = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(_DIR, "..", "www", "nachbarschaft_laden_logo.svg")
out_path = os.path.join(_DIR, "images", "logo.PNG")

# Render SVG as-is (transparent background) to find actual content bounds
scale = 4
png_data = cairosvg.svg2png(url=svg_path, scale=scale)
img = Image.open(io.BytesIO(png_data)).convert('RGBA')

# Crop to non-transparent area (the rounded-rect background)
a = np.array(img.split()[3])
rows = np.any(a > 10, axis=1)
cols = np.any(a > 10, axis=0)
row_i = np.where(rows)[0]
col_i = np.where(cols)[0]
print(f'Non-transparent: y={row_i[0]}-{row_i[-1]}, x={col_i[0]}-{col_i[-1]}')

x0, y0 = col_i[0], row_i[0]
x1, y1 = col_i[-1] + 1, row_i[-1] + 1
img_cropped = img.crop((x0, y0, x1, y1)).convert('RGB')
print(f'Cropped: {img_cropped.size}, aspect: {img_cropped.width/img_cropped.height:.3f}')

img_cropped.save(out_path)
print('Saved ok')
