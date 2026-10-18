#!/usr/bin/env python3
"""Rebuild the reference package from Tesla's official replay; no app code changes.

Requires ffmpeg, ffprobe, and Pillow. Pass the downloaded full replay as argv[1].
Example acquisition (yt-dlp):
  yt-dlp -f 248+251 --merge-output-format webm -o official-event.webm \
    'https://www.youtube.com/watch?v=qt5p-_tE8d0'
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.youtube.com/watch?v=qt5p-_tE8d0"
SPECS = [
    ("A01", 368, "First run: rear view at the foot of the ramp"),
    ("A02", 392, "First run: entry into the curve"),
    ("A03", 396, "First run: car on the steep surface"),
    ("A04", 406, "First run: inverted close-up; HUD pitch 170 deg, altitude 67.7 ft"),
    ("A05", 412, "First run: held near the top; HUD altitude 69.1 ft"),
    ("A06", 416, "First run: reversing down while wheels remain on the surface"),
    ("A07", 424, "First run: back at the bottom"),
    ("B01", 428, "Second run: ready at the bottom"),
    ("B02", 431, "Second run: entering the curve"),
    ("B03", 433, "Second run: steep ascent"),
    ("B04", 435, "Second run: near the overhang"),
    ("B05", 436, "Second run: crossing the lip, near-inverted"),
    ("B06", 436.5, "Second run: visibly leaving the lip; side plume"),
    ("B07", 437, "Second run: detached, rotating beside the ramp"),
    ("B08", 437.5, "Second run: underside visible, approaching wheels-down"),
    ("B09", 438, "Second run: upright descent; several downward jets"),
    ("B10", 438.5, "Second run: jets meeting the ground and building a cloud"),
    ("B11", 439, "Second run: low descent above expanding vapor"),
    ("B12", 439.5, "Second run: landing zone increasingly obscured"),
    ("B13", 440.5, "Second run: low/landing phase behind cloud; tire contact obscured"),
    ("B14", 442, "Second run: car visible on the ground after landing"),
    ("B15", 446, "Post-run overhead view: car on the apron"),
    ("R01", 453.5, "Close replay: lip and inverted car"),
    ("R02", 454.5, "Close replay: car turning away from the surface"),
    ("R03", 455.5, "Close replay: underbody and asymmetrical plume directions"),
    ("R04", 456, "Close replay: underbody detail and side/downward jets"),
    ("R05", 458, "Close replay: wheels-down descent and vertical jet columns"),
    ("R06", 460, "Close replay: low descent into vapor"),
    ("R07", 464.5, "Aerial replay: inverted wheel contact under the overhang"),
    ("R08", 466.5, "Aerial replay: departure from the lip"),
    ("R09", 467, "Aerial replay: exposed underside and multiple jets"),
    ("R10", 469, "Aerial replay: body upright above the apron"),
    ("F01", 670, "Separate fleet stunt: lineup including the Semi"),
    ("F02", 672, "Separate fleet stunt: upward departure"),
    ("F03", 673, "Separate fleet stunt: airborne rotation above the lineup"),
    ("F04", 674, "Separate fleet stunt: wheels-down descent"),
    ("F05", 675, "Separate fleet stunt: landing cloud"),
    ("D01", 578, "Model reference: side profile"),
    ("D02", 661, "Model reference: front three-quarter view"),
    ("D03", 810, "Model reference: rear light bar, four rear nozzles, diffuser"),
]
CLIPS = [
    ("ramp-event_0603-0756.mp4", 363, 476),
    ("ramp-main_0708-0726.mp4", 428, 446),
    ("fleet_1056-1149.mp4", 656, 709),
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stamp(seconds):
    return f"{int(seconds // 60):02}-{seconds % 60:06.3f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--skip-clips", action="store_true")
    args = parser.parse_args()
    for folder in ("frames", "contact-sheets", "media"):
        (ROOT / folder).mkdir(exist_ok=True)
    metadata = json.loads((ROOT / "source-metadata.json").read_text())
    if digest(args.source) != metadata["source_sha256"]:
        raise SystemExit("Source differs from the documented replay download; verify it before updating the package.")

    frames = []
    for frame_id, requested, note in SPECS:
        relative = f"frames/{frame_id}_event_{stamp(requested)}.jpg"
        cmd = ["ffmpeg", "-hide_banner", "-copyts", "-ss", str(requested),
               "-i", str(args.source), "-map", "0:v:0", "-frames:v", "1",
               "-vf", "showinfo", "-q:v", "2", "-update", "1",
               str(ROOT / relative), "-y"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        pts = float(re.search(r"n:\s*0\s+pts:.*?pts_time:([\d.]+)", result.stderr)[1])
        frames.append({"id": frame_id, "requested_event_seconds": requested,
                       "decoded_source_pts_seconds": pts,
                       "source_frame_index_0_based": round(pts * 30000 / 1001),
                       "file": relative, "source_link": f"{URL}&t={int(requested)}s",
                       "note": note, "sha256": digest(ROOT / relative)})
    (ROOT / "frames.json").write_text(json.dumps(frames, indent=2) + "\n")

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 21)
    except OSError:
        font = ImageFont.load_default(size=21)
    groups = [("01-first-run", "A"), ("02-main-jump", "B"),
              ("03-replay-angles", "R"), ("04-fleet-context", "F"),
              ("05-car-details", "D")]
    for name, prefix in groups:
        selected = [frame for frame in frames if frame["id"].startswith(prefix)]
        sheet = Image.new("RGB", (4 * 480, math.ceil(len(selected) / 4) * 304), "#151515")
        draw = ImageDraw.Draw(sheet)
        for i, frame in enumerate(selected):
            with Image.open(ROOT / frame["file"]) as img:
                img.thumbnail((480, 270))
                x, y = (i % 4) * 480, (i // 4) * 304
                sheet.paste(img, (x, y))
            time = stamp(frame["requested_event_seconds"]).replace("-", ":")
            draw.text((x + 8, y + 276), f"{frame['id']}  event {time}", font=font, fill="white")
        sheet.save(ROOT / "contact-sheets" / f"{name}.jpg", quality=92)

    if not args.skip_clips:
        clips = []
        for name, start, end in CLIPS:
            print(f"Encoding {name}", flush=True)
            path = ROOT / "media" / name
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start),
                            "-i", str(args.source), "-t", str(end - start),
                            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                            str(path), "-y"], check=True)
            clips.append({"file": f"media/{name}", "event_start_seconds": start,
                          "event_end_seconds": end, "nominal_duration_seconds": end - start,
                          "timing_note": "Local time zero maps to nominal source start; allow one video frame of rounding.",
                          "sha256": digest(path), "bytes": path.stat().st_size})
        (ROOT / "clips.json").write_text(json.dumps(clips, indent=2) + "\n")
    print(f"Extracted {len(frames)} full-resolution reference frames.")


if __name__ == "__main__":
    main()
