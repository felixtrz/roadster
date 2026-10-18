#!/usr/bin/env python3
"""Roadster's approval-gated Tripo V3 client (Python standard library only).

The API credential is read directly from macOS Keychain in this process. It is
never passed on a command line, written to disk, included in errors, or sent on
downloads. Generation is never retried automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "art/roadster/tripo"
BASE = "https://openapi.tripo3d.ai/v3"
VIEWS = ("front", "left", "back", "right")
MODELS = ("v3.1-20260211", "v3.0-20250812", "v2.5-20250123", "P1-20260311", "P2-20260801")
DEFAULT_PARAMETERS = {
    "model": "v3.1-20260211",
    "face_limit": 200000,
    "geometry_quality": "detailed",
    "texture": True,
    "pbr": True,
    "texture_quality": "detailed",
    "texture_alignment": "original_image",
    "model_seed": 20261017,
    "texture_seed": 20261017,
}


class TripoError(Exception):
    """A deliberately sanitized error suitable for a user-visible log."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    with Path(path).open() as stream:
        return json.load(stream)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def project_path(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def relative_path(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def keychain_token():
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-a", "tripo", "-s", "tripo-api", "-w"],
        capture_output=True, timeout=30, check=False,
    )
    if result.returncode:
        raise TripoError("Tripo Keychain entry unavailable")
    token = result.stdout.decode("utf-8").strip()
    if not token.startswith("tsk_") or any(c.isspace() for c in token):
        raise TripoError("Tripo Keychain entry has an unexpected credential format")
    return token


class Client:
    def __init__(self):
        self._token = keychain_token()
        self._opener = urllib.request.build_opener(NoRedirect())

    def api(self, endpoint, payload=None, raw=None, content_type="application/json"):
        # Caller controls only a relative path; credentials have one destination.
        if not re.fullmatch(r"/(?:account/(?:balance|usage)|files|generation/multiview-to-model|tasks/[A-Za-z0-9_-]+)", endpoint):
            raise TripoError("Invalid API endpoint")
        body = json.dumps(payload).encode() if payload is not None else raw
        request = urllib.request.Request(
            BASE + endpoint,
            data=body,
            headers={"Authorization": "Bearer " + self._token,
                     "Content-Type": content_type, "Accept": "application/json"},
            method="POST" if body is not None else "GET",
        )
        try:
            with self._opener.open(request, timeout=60) as response:
                result = json.loads(response.read(8_000_000))
        except urllib.error.HTTPError as error:
            api_code = None
            try:
                candidate = json.loads(error.read(65536)).get("code")
                api_code = candidate if isinstance(candidate, int) else None
            except Exception:
                pass
            raise TripoError(f"HTTP {error.code}, API code {api_code}; no automatic retry") from None
        except Exception as error:
            raise TripoError(f"API transport failed ({type(error).__name__}); outcome may be unknown") from None
        if not isinstance(result, dict):
            raise TripoError("Unexpected API response")
        if result.get("code", 0) != 0:
            code = result.get("code")
            raise TripoError(f"API code {code if isinstance(code, int) else 'unknown'}; no automatic retry")
        return result.get("data", {})

    def balance(self):
        data = self.api("/account/balance")
        return {key: data[key] for key in ("balance", "frozen") if key in data}

    def upload(self, image):
        image = Path(image)
        data = image.read_bytes()
        if image.suffix.lower() not in (".png", ".jpg", ".jpeg") or len(data) > 20_000_000:
            raise TripoError("Uploads must be PNG/JPEG no larger than 20 MB")
        boundary = "RoadsterUpload" + uuid.uuid4().hex
        mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
        # Fixed filename avoids putting arbitrary filenames into multipart headers.
        filename = "roadster" + image.suffix.lower()
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f"Content-Type: {mime}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        result = self.api("/files", raw=body, content_type="multipart/form-data; boundary=" + boundary)
        token = result.get("file_token")
        if not isinstance(token, str) or not token:
            raise TripoError("Upload response omitted file_token")
        return token

    def task(self, task_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
            raise TripoError("Invalid task id")
        return self.api("/tasks/" + task_id)


def validate_manifest(path, require_approval=False):
    manifest = read_json(path)
    images = manifest.get("images", {})
    if not isinstance(images, dict) or "front" not in images or not 2 <= len(images) <= 4:
        raise TripoError("Manifest needs front and at least one other named view")
    if set(images) - set(VIEWS):
        raise TripoError("Manifest has an unsupported view; use front/left/back/right")
    for view, record in images.items():
        image = project_path(record["path"])
        if not image.is_file() or sha256(image) != record.get("sha256"):
            raise TripoError(f"Image missing or changed after review: {view}")
    if require_approval:
        judgments = manifest.get("judgments", [])
        if manifest.get("approved") is not True or len(judgments) < 2:
            raise TripoError("Two independent image judges must approve before uploading/generation")
        identities = set()
        for judgment in judgments:
            judge = judgment.get("judge")
            score = judgment.get("score")
            if not isinstance(judge, str) or not judge.strip() or judge in identities:
                raise TripoError("Judges must have distinct nonempty identities")
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 9 <= score <= 10:
                raise TripoError("Every recorded judge must score the images at least 9/10")
            if not project_path(judgment.get("report", "")).is_file():
                raise TripoError("Each judge must have a saved evidence report")
            identities.add(judge)
    parameters = {**DEFAULT_PARAMETERS, **manifest.get("parameters", {})}
    if set(parameters) - set(DEFAULT_PARAMETERS):
        raise TripoError("Unknown generation parameter")
    if parameters["model"] not in MODELS:
        raise TripoError("Unsupported pinned model version")
    if not isinstance(parameters["face_limit"], int) or parameters["face_limit"] <= 0:
        raise TripoError("face_limit must be a positive integer")
    if parameters["geometry_quality"] not in ("standard", "detailed"):
        raise TripoError("geometry_quality must be standard or detailed")
    if parameters["texture_quality"] not in ("standard", "detailed", "extreme"):
        raise TripoError("texture_quality must be standard, detailed, or extreme")
    if parameters["pbr"] and not parameters["texture"]:
        raise TripoError("pbr forces texture; disable both for a geometry-only reference")
    if parameters["model"].startswith("P") or parameters["model"] == "v2.5-20250123":
        parameters.pop("geometry_quality")
    if parameters["model"] == "v2.5-20250123":
        parameters.pop("texture_quality")
    h_face_limits = {"v3.1-20260211": 2000000 if parameters.get("geometry_quality") == "detailed" else 1500000,
                     "v3.0-20250812": 2000000 if parameters.get("geometry_quality") == "detailed" else 1000000,
                     "v2.5-20250123": 500000}
    if parameters["model"] in h_face_limits and parameters["face_limit"] > h_face_limits[parameters["model"]]:
        raise TripoError("face_limit exceeds this H-series model's supported limit")
    if parameters["model"] == "P1-20260311" and parameters["face_limit"] > 20000:
        raise TripoError("P1 supports at most 20,000 faces")
    if parameters["model"] == "P2-20260801" and parameters["face_limit"] > 50000:
        raise TripoError("P2 triangle output supports at most 50,000 faces")
    return manifest, parameters


def estimated_credits(parameters):
    # Public list prices; account discounts and actual task charges may differ.
    value = 40 if parameters["model"].startswith("P") else 20
    if parameters.get("texture"):
        value += {"standard": 10, "detailed": 20, "extreme": 30}[parameters.get("texture_quality", "standard")]
    if parameters.get("geometry_quality") == "detailed":
        value += 20
    return value


def payload_for(manifest, parameters, uploads=None):
    uploads = uploads or {}
    return {"inputs": [{view: uploads.get(view, f"<{view}_file_token>")}
                       for view in VIEWS if view in manifest["images"]], **parameters}


def load_run(path):
    path = project_path(path)
    try:
        path.relative_to(ART.resolve())
    except ValueError:
        raise TripoError("Run directory must be under art/roadster/tripo") from None
    path.mkdir(parents=True, exist_ok=True)
    state_file = path / "ledger.json"
    return path, state_file, read_json(state_file) if state_file.exists() else {}


def approved_for_run(manifest_path, state):
    manifest, parameters = validate_manifest(manifest_path, require_approval=True)
    digest = sha256(manifest_path)
    if state.get("manifest_sha256", digest) != digest:
        raise TripoError("Run manifest changed; use a fresh run directory")
    state.update({"manifest": relative_path(manifest_path), "manifest_sha256": digest})
    return manifest, parameters


def task_summary(task):
    return {k: task[k] for k in ("task_id", "status", "progress", "credits_consumed", "error_code",
                                "created_at", "completed_at") if k in task}


def download_outputs(task, directory):
    output = task.get("output", {})
    candidates = {}

    def collect(value, label):
        if isinstance(value, str) and value.startswith("https://"):
            candidates[label] = value
        elif isinstance(value, dict):
            for key, item in value.items():
                collect(item, label + "_" + key if label else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                collect(item, label + "_" + str(index))

    collect(output, "")
    results = []
    opener = urllib.request.build_opener(NoRedirect())
    for label, url in candidates.items():
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
        if not any(host == root or host.endswith("." + root) for root in ("tripo3d.ai", "tripo3d.com")):
            raise TripoError("Output URL is outside official Tripo domains")
        suffix = Path(parsed.path).suffix.lower()
        if suffix not in (".glb", ".gltf", ".fbx", ".obj", ".zip", ".png", ".jpg", ".jpeg", ".webp"):
            continue
        name = re.sub(r"[^A-Za-z0-9_-]", "_", label) + suffix
        destination = directory / name
        temporary = destination.with_suffix(destination.suffix + ".part")
        # No Authorization header: signed output URLs authorize their own downloads.
        try:
            with opener.open(urllib.request.Request(url), timeout=60) as response, temporary.open("wb") as stream:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 512_000_000:
                        raise TripoError("Output exceeds 512 MB download limit")
                    stream.write(chunk)
            os.replace(temporary, destination)
        except Exception as error:
            temporary.unlink(missing_ok=True)
            if isinstance(error, TripoError):
                raise
            raise TripoError(f"Output download failed ({type(error).__name__})") from None
        results.append({"file": relative_path(destination), "bytes": destination.stat().st_size,
                        "sha256": sha256(destination)})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("manifest", "plan", "credential-check", "balance", "upload", "submit", "status", "poll", "download"))
    parser.add_argument("--manifest", default="art/roadster/tripo/approved-images.json")
    parser.add_argument("--run", default="art/roadster/tripo/h31-reference-v1")
    parser.add_argument("--front")
    parser.add_argument("--left")
    parser.add_argument("--back")
    parser.add_argument("--right")
    parser.add_argument("--execute", action="store_true", help="Required for a billable generation submission")
    parser.add_argument("--max-credits", type=float, default=60)
    parser.add_argument("--wait-seconds", type=float, default=45)
    args = parser.parse_args()
    manifest_path = project_path(args.manifest)
    if args.action == "manifest":
        if manifest_path.exists():
            raise TripoError("Manifest already exists; edit it explicitly or select a new path")
        images = {}
        for view in VIEWS:
            if value := getattr(args, view):
                path = project_path(value)
                images[view] = {"path": relative_path(path), "sha256": sha256(path)}
        manifest = {"approved": False, "images": images, "judgments": [], "parameters": DEFAULT_PARAMETERS}
        write_json(manifest_path, manifest)
        validate_manifest(manifest_path)
        emit({"manifest": relative_path(manifest_path), "status": "awaiting_independent_judges"})
        return
    if args.action == "plan":
        manifest, parameters = validate_manifest(manifest_path)
        emit({"endpoint": BASE + "/generation/multiview-to-model", "request": payload_for(manifest, parameters),
              "estimated_credits": estimated_credits(parameters), "approved": manifest.get("approved", False)})
        return
    if args.action == "credential-check":
        keychain_token()
        emit({"credential_available": True, "service": "tripo-api", "account": "tripo"})
        return
    if args.action == "balance":
        emit(Client().balance())
        return
    directory, state_file, state = load_run(args.run)
    if args.action in ("upload", "submit"):
        manifest, parameters = approved_for_run(manifest_path, state)
        if state.get("submission_intent"):
            if state.get("task_id"):
                emit({"status": "already_submitted", "task_id": state["task_id"]})
                return
            raise TripoError("Submission outcome unknown; reconcile account usage before any new generation")
        client = Client()
        if args.action == "upload":
            uploads = state.setdefault("uploads", {})
            state.setdefault("balance_before", client.balance())
            for view in VIEWS:
                if view in manifest["images"] and view not in uploads:
                    uploads[view] = client.upload(project_path(manifest["images"][view]["path"]))
                    write_json(state_file, state)
                    emit({"status": "uploaded", "view": view})
            return
        if not args.execute:
            raise TripoError("Billable submit requires --execute after independent image approval")
        cost = estimated_credits(parameters)
        if cost > args.max_credits:
            raise TripoError("Estimated generation price exceeds --max-credits")
        uploads = state.get("uploads", {})
        if set(uploads) != set(manifest["images"]):
            raise TripoError("Upload the complete approved view set first")
        request = payload_for(manifest, parameters, uploads)
        balance = client.balance()
        if balance.get("balance", 0) < cost:
            raise TripoError("Insufficient available balance for estimated generation price")
        state.update({"submission_intent": now(), "request": request, "estimated_credits": cost,
                      "balance_before_submit": balance})
        write_json(state_file, state)  # Never duplicate a timed-out billable POST.
        result = client.api("/generation/multiview-to-model", request)
        if not result.get("task_id"):
            raise TripoError("Submission returned no task id; reconcile usage before retrying")
        state["task_id"] = result["task_id"]
        write_json(state_file, state)
        emit({"status": "submitted", "task_id": state["task_id"], "estimated_credits": cost})
        return
    if not state.get("task_id"):
        raise TripoError("No submitted task in this run")
    client = Client()
    end = time.monotonic() + min(max(args.wait_seconds, 0), 55)
    while True:
        task = client.task(state["task_id"])
        # Store signed output URLs only in the project-local artifact ledger.
        state["task"] = task
        write_json(state_file, state)
        emit(task_summary(task))
        if args.action != "poll" or task.get("status") in ("success", "failed", "cancelled") or time.monotonic() >= end:
            break
        time.sleep(min(5, max(0, end - time.monotonic())))
    if task.get("status") in ("success", "failed", "cancelled"):
        state["balance_after"] = client.balance()
        write_json(state_file, state)
    if args.action == "download":
        if task.get("status") != "success":
            raise TripoError("Task must succeed before download")
        state["downloads"] = download_outputs(task, directory)
        write_json(state_file, state)
        emit({"downloads": state["downloads"], "balance_after": state.get("balance_after")})


if __name__ == "__main__":
    try:
        main()
    except TripoError as error:
        emit({"status": "stopped", "reason": str(error)})
        sys.exit(1)
    except Exception as error:
        # Do not print exception strings/tracebacks that may contain signed URLs.
        emit({"status": "stopped", "error_type": type(error).__name__})
        sys.exit(1)
