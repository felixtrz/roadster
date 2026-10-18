import sys
from PIL import Image
out, files = sys.argv[1], sys.argv[2:]
ims = [Image.open(f).convert('RGB') for f in files]
w = 520; ims = [i.resize((w, int(i.height * w / i.width))) for i in ims]
cols = 3 if len(ims) > 4 else 2
rows = (len(ims) + cols - 1) // cols
h = max(i.height for i in ims)
M = Image.new('RGB', (cols * w, rows * h), (30, 30, 30))
for k, i in enumerate(ims): M.paste(i, ((k % cols) * w, (k // cols) * h))
M.save(out, quality=72)
