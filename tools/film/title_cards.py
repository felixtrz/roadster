"""Draws the film's title cards as transparent 1920x1080 PNGs (ffmpeg here has no drawtext).

    python3 tools/film/title_cards.py <out_dir>   -> title-open.png, title-xr.png, title-end.png
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONTS = {
    'bold': ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'],
    'regular': ['/System/Library/Fonts/Supplemental/Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'],
}


def font(kind, size):
    for path in [os.environ.get('FILM_FONT_' + kind.upper(), '')] + FONTS[kind]:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def card(path, lines, y0=0.40, band=False):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if band:
        # soft dark band behind the text so it reads over a bright subject
        from PIL import ImageFilter
        b = Image.new('L', (W, H), 0)
        ImageDraw.Draw(b).rectangle((0, int(H * y0) - 60, W, int(H * y0) + 150), fill=150)
        im.putalpha(b.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(im)
    y = H * y0
    for text, size, kind, col, track in lines:
        f = font(kind, size)
        widths = [d.textlength(c, font=f) for c in text]
        x = (W - sum(widths) - track * (len(text) - 1)) / 2
        for dx, dy, shadow in ((0, 3, True), (0, 0, False)):
            xx = x
            for c, w in zip(text, widths):
                d.text((xx + dx, y + dy), c, font=f, fill=(0, 0, 0, 140) if shadow else col)
                xx += w + track
        y += size * 1.45
    im.save(path)


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    card(os.path.join(out, 'title-open.png'), [('ROADSTER', 84, 'bold', (255, 255, 255, 255), 26),
         ('THE RAMP  ·  McGREGOR, TEXAS  ·  RECREATED IN WEBXR', 26, 'regular', (214, 220, 228, 235), 4)], y0=0.70, band=True)
    card(os.path.join(out, 'title-xr.png'), [('STEP INSIDE', 68, 'bold', (255, 255, 255, 255), 18),
         ('WebXR  ·  emulated Meta Quest 3', 28, 'regular', (208, 214, 222, 235), 2)])
    card(os.path.join(out, 'title-end.png'), [('ROADSTER', 72, 'bold', (255, 255, 255, 255), 22),
         ('THE RAMP  ·  recreated in WebXR', 28, 'regular', (208, 214, 222, 235), 3)])
