"""
Copyright 2022 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from io import BytesIO
import logging
from os import environ
from pathlib import Path
from typing import Iterator

import docai
from flask import Flask
from flask import jsonify
from flask import request
from flask import send_from_directory
from flask.wrappers import Response
from google.api_core.exceptions import BadRequest
import google.auth

STATIC_FOLDER = "frontend"
SAMPLES_PATH = Path("./samples")

_, PROJECT_ID = google.auth.default()
assert isinstance(PROJECT_ID, str)

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path="")


@app.get("/")
def index():
    return send_from_directory(STATIC_FOLDER, "index.html", etag=ETAG)


@app.get("/<string:filename>")
def static_file(filename: str):
    return send_from_directory(STATIC_FOLDER, filename, etag=ETAG)


@app.get("/api/samples")
def samples():
    def get_samples(
        parent_path: Path,
        rel_dir: str = "",
    ) -> Iterator[tuple[str, list[str]]]:
        paged_samples: list[str] = []
        for path in parent_path.glob("*"):
            if path.is_dir():
                sub_dir = f"{rel_dir}/{path.name}" if rel_dir else path.name
                yield from get_samples(path, sub_dir)
            elif path.suffix[1:].lower() in SUFFIXES:
                if rel_dir:
                    paged_samples.append(f"{rel_dir}/{path.name}")
                else:
                    yield path.stem, [path.name]
        if paged_samples:
            yield parent_path.name, sorted(paged_samples)

    # See https://cloud.google.com/document-ai/docs/file-types#other_processors
    SUFFIXES = {"pdf", "tiff", "tif", "gif", "jpeg", "jpg", "png", "bmp", "webp"}
    samples = dict(get_samples(SAMPLES_PATH))

    # Note: jsonify sorts dictionaries by key by default
    return jsonify(samples=samples)


@app.get("/api/samples/<path:file_path>")
def sample_file(file_path: str):
    return send_from_directory(SAMPLES_PATH, file_path, etag=ETAG)


@app.get("/api/project")
def project():
    return jsonify(project=PROJECT_ID)


@app.get("/api/processors/locations")
def processors_locations():
    locations = docai.processor_locations()

    return jsonify(locations=locations)


@app.get("/api/processors/<string:project_id>/<string:api_location>")
def id_processors(project_id: str, api_location: str):
    processors = docai.frontend_id_processors(project_id, api_location)

    return jsonify(processors=processors)


@app.get("/api/processor/fields/<string:proc_info>")
def processor_fields(proc_info: str):
    processor = docai.processor_from_frontend_proc_info(proc_info)
    if processor is None:
        return f"Incorrect processor info: {proc_info}", 400

    fields = docai.get_processor_fields(processor)

    return jsonify(fields=fields)


@app.post("/api/processor/analysis/<string:proc_info>")
def processor_analysis(proc_info: str):
    processor = docai.processor_from_frontend_proc_info(proc_info)
    if processor is None:
        return f"Incorrect processor info: {proc_info}", 400
    photos = request.files.getlist("photos[]")
    if not photos:
        return 'Missing "photos[]" image(s)', 400

    files = [(BytesIO(p.read()), p.mimetype) for p in photos]

    try:
        document = docai.process_files(files, processor)
    except BadRequest as e:
        logging.error(message := str(e))
        return message, 400
    except Exception as e:
        logging.exception(message := str(e))
        return message, 500

    analysis = docai.id_data_from_document(document)

    return jsonify(analysis=analysis)


@app.get("/admin/processors/check")
def check_processors():
    docai.check_create_processors(PROJECT_ID)

    return "check_processors: done (see logs)\n"


# Web apps deployed in a Buildpacks image have their source file timestamps zeroed
BUILDPACKS_IMAGE_TIMESTAMP = "Tue, 01 Jan 1980 00:00:01 GMT"
# Enable ETag caching on static files deployed in Buildpacks images
# Revision env. variable: "K_REVISION" for Cloud Run, "GAE_VERSION" for App Engine
IMAGE_VERSION = environ.get("K_REVISION", "") or environ.get("GAE_VERSION", "")
ETAG = IMAGE_VERSION if IMAGE_VERSION else True


@app.before_request
def before_request():
    if request.environ.get("HTTP_IF_MODIFIED_SINCE") == BUILDPACKS_IMAGE_TIMESTAMP:
        # Fix caching issue with incorrect 304 responses that occur if the browser
        # previously received a wrong "Last-Modified" response
        del request.environ["HTTP_IF_MODIFIED_SINCE"]


@app.after_request
def after_request(response: Response) -> Response:
    if response.headers.get("Last-Modified") == BUILDPACKS_IMAGE_TIMESTAMP:
        # The modification time is actually unknown
        response.headers.remove("Last-Modified")

    return response


if __name__ == "__main__":
    # Dev only: run "python main.py" (3.10+) and open http://localhost:8080
    logging.getLogger().setLevel(logging.DEBUG)
    app.run(host="localhost", port=8080, debug=True)
