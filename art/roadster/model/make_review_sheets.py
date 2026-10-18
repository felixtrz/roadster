"""Assemble evidence without altering individual render bytes."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
try:
    FONT=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
except OSError:
    FONT=ImageFont.load_default()

views=['front','left','back','top','quarter','rear-quarter','low-front','low-quarter','underside']
sheet=Image.new('RGB',(1920,1940),'#f3f3f3');draw=ImageDraw.Draw(sheet)
draw.text((16,8),'Authored Roadster V4 — material and clay; independent score pending',fill='black',font=FONT)
for index,(view,mode) in enumerate((view,mode) for view in views for mode in ('material','clay')):
    tile=Image.open(ROOT/'renders'/f'{mode}-{view}.png').convert('RGB').resize((480,360))
    x=(index%4)*480;y=40+(index//4)*380
    sheet.paste(tile,(x,y+20));draw.text((x+10,y),f'{view} | {mode}',fill='black',font=FONT)
sheet.save(ROOT/'renders/contact.png')

views=views[:-1]
comparison=Image.new('RGB',(1280,len(views)*510+40),'white');draw=ImageDraw.Draw(comparison)
draw.text((12,8),'Same-camera generated reference / authored V4 — generated reference is fallible',fill='black',font=FONT)
for row,view in enumerate(views):
    y=40+row*510
    for col,(folder,label) in enumerate([('reference/renders','Generated reference'),('renders','Authored V4')]):
        tile=Image.open(ROOT/folder/f'material-{view}.png').convert('RGB')
        comparison.paste(tile,(col*640,y+26))
        draw.text((col*640+12,y+3),f'{view} | {label}',fill='black',font=FONT)
comparison.save(ROOT/'source-comparison.png')
print('Updated18-view contact and8-view source comparison sheets.')
