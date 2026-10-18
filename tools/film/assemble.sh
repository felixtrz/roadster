#!/bin/bash
# Edits captured frames into artifacts/film/roadster-film.mp4, all at real time (no slow motion):
#   1. the whole run in the browser app (artifacts/film/2d, from capture-all.sh + plan-2d.json);
#   1b. the onboard replay on the Mounted view (artifacts/film/mounted, plan-mounted.json);
#   2. a few seconds of the broadcast with the computer-vision reconstruction drawn over it
#      (artifacts/film/cv, from annotate_cv.py; skipped if absent, e.g. without the local footage);
#   3. the shorter "step inside" XR shot (artifacts/film/xr, from capture-all.sh + plan-xr.json);
#   4. an end card, then the studio outro with its sound (FILM_OUTRO; skipped if absent).
# Segment 2 contains Tesla footage, so the film is not part of the published repository.
# Needs ffmpeg and python3 with Pillow (title cards are drawn as PNG overlays).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/artifacts/film"
python3 "$ROOT/tools/film/title_cards.py" .
XF=0.5; END=2.2
dur() { python3 -c "print(round($(ls "$1" | wc -l)/30, 3))"; }
# light bloom and grade, applied on the YUV side (eq on gbrp shifts the hue)
GRADE="format=gbrp,split[a][b];[b]gblur=sigma=14[g];[a][g]blend=all_mode=screen:all_opacity=0.25,format=yuv420p,eq=brightness=0.015:contrast=1.05:saturation=1.08"
D2=$(dur 2d)
ffmpeg -v error -y -framerate 30 -i 2d/f%05d.png -loop 1 -t "$D2" -i title-open.png -filter_complex \
  "[0:v]$GRADE,format=rgba[base];[1:v]format=rgba,fade=t=in:st=0.8:d=0.9:alpha=1,fade=t=out:st=4.6:d=0.9:alpha=1[t];[base][t]overlay=0:0:shortest=1,format=yuv420p,setsar=1" \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p part-2d.mp4
DM=$(dur mounted)
ffmpeg -v error -y -framerate 30 -i mounted/f%05d.png -loop 1 -t "$DM" -i title-onboard.png -filter_complex \
  "[0:v]$GRADE,format=rgba[base];[1:v]format=rgba,fade=t=in:st=0.2:d=0.5:alpha=1,fade=t=out:st=2.4:d=0.5:alpha=1[t];[base][t]overlay=0:0:shortest=1,format=yuv420p,setsar=1" \
  -c:v libx264 -preset slow -crf 16 part-mounted.mp4
DX=$(dur xr)
ffmpeg -v error -y -framerate 30 -i xr/f%05d.png -loop 1 -t "$DX" -i title-xr.png -filter_complex \
  "[0:v]$GRADE,format=rgba[base];[1:v]format=rgba,fade=t=in:st=0.2:d=0.5:alpha=1,fade=t=out:st=2.0:d=0.5:alpha=1[t];[base][t]overlay=0:0:shortest=1,format=yuv420p,setsar=1" \
  -c:v libx264 -preset slow -crf 16 part-xr.mp4
ffmpeg -v error -y -f lavfi -t "$END" -i color=c=black:s=1920x1080:r=30 -loop 1 -t "$END" -i title-end.png -filter_complex \
  "[0:v][1:v]overlay=0:0,fade=t=in:st=0:d=0.5,format=yuv420p,setsar=1" -c:v libx264 -preset slow -crf 16 part-end.mp4
PARTS=(part-2d.mp4 part-mounted.mp4)
if [ -d cv ] && [ "$(ls cv | wc -l)" -gt 0 ]; then
  ffmpeg -v error -y -framerate 30 -i cv/f%05d.png -vf "format=yuv420p,setsar=1" -c:v libx264 -preset slow -crf 16 part-cv.mp4
  PARTS+=(part-cv.mp4)
fi
PARTS+=(part-xr.mp4)
# chain the parts with short fades through black, then the end card
INPUTS=(); FILTER=""; OFF=0; PREV="[0:v]"
for i in "${!PARTS[@]}"; do INPUTS+=(-i "${PARTS[$i]}"); done
for ((i = 1; i < ${#PARTS[@]}; i++)); do
  D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${PARTS[$((i - 1))]}")
  OFF=$(python3 -c "print(round($OFF + $D - $XF, 3))")
  FILTER+="${PREV}[$i:v]xfade=transition=fadeblack:duration=$XF:offset=$OFF[x$i];"
  PREV="[x$i]"
done
N=${#PARTS[@]}
FILTER+="${PREV}[$N:v]concat=n=2:v=1,format=yuv420p[v]"
ffmpeg -v error -y "${INPUTS[@]}" -i part-end.mp4 -filter_complex "$FILTER" \
  -map "[v]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -movflags +faststart roadster-film-main.mp4
# Studio outro with its sound (FILM_OUTRO, default: the sibling brand-site project); the film itself is silent.
OUTRO="${FILM_OUTRO:-$ROOT/../elixr-games-brand/public/brand/elixr-original-no-ring-sound-1080p.mp4}"
if [ -f "$OUTRO" ]; then
  DMAIN=$(ffprobe -v error -show_entries format=duration -of csv=p=0 roadster-film-main.mp4)
  ffmpeg -v error -y -i roadster-film-main.mp4 -f lavfi -t "$DMAIN" -i anullsrc=r=48000:cl=stereo -i "$OUTRO" -filter_complex \
    "[0:v]fps=30,setsar=1,format=yuv420p[v0];[2:v]scale=1920:1080,fps=30,setsar=1,format=yuv420p[v1];[2:a]aresample=48000,aformat=channel_layouts=stereo[a1];[v0][1:a][v1][a1]concat=n=2:v=1:a=1[v][a]" \
    -map "[v]" -map "[a]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart roadster-film.mp4
else
  echo "no outro at $OUTRO; the film ends on the title card"
  mv roadster-film-main.mp4 roadster-film.mp4
fi
ffprobe -v error -show_entries format=duration,size -of csv=p=0 roadster-film.mp4
