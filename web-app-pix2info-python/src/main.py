"""
Copyright 2023 Google LLC

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
import functools
from io import BytesIO
import logging
from pathlib import Path

from backend import docai
from backend import processors
from backend import render
from backend import samples
from flask import Flask
from flask import jsonify
from flask import request
from flask import send_file
from flask import send_from_directory
from google.api_core.exceptions import BadRequest
from google.api_core.exceptions import ClientError
import google.auth

STATIC_FOLDER = "frontend"
SAMPLES_ROOT = Path("./samples")

_, PROJECT_ID = google.auth.default()
assert isinstance(PROJECT_ID, str)

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path="")
with app.app_context():
    from backend.etag import ETAG


@app.get("/")
def get_homepage():
    return send_from_directory(STATIC_FOLDER, "index.html", etag=ETAG)


@app.get("/<string:filename>")
def get_static_file(filename: str):
    return send_from_directory(STATIC_FOLDER, filename, etag=ETAG)


@app.get("/api/samples")
def get_samples():
    demo_samples = samples.get_samples(SAMPLES_ROOT)

    # Note: jsonify sorts keys by default (i.e. sorting is not needed in frontend)
    return jsonify(demo_samples)


@app.get("/api/processors/locations")
def get_processors_locations():
    processor_locations = processors.DEMO_PROCESSING_LOCATIONS

    return jsonify(processor_locations)


@app.get("/api/processors/<string:location>")
def get_demo_processors(location: str):
    demo_processors = docai.frontend_demo_processors(PROJECT_ID, location)

    return jsonify(demo_processors)


def api_post_request(func):
    @functools.wraps(func)
    def wrapper_api_request(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, BadRequest, ClientError) as e:
            logging.error(message := str(e))
            return message, 400
        except Exception as e:
            logging.exception(message := str(e))
            return message, 500

    return wrapper_api_request


def analysis_request(document_data: docai.DocumentData):
    document, json = document_data
    summary = dict(counts=docai.summary_counts_for_document(document))

    return jsonify(json=json, summary=summary)


@app.post("/api/analysis/sample/<string:processor_name>/<string:sample_name>")
@api_post_request
def sample_analysis(processor_name: str, sample_name: str):
    paths = request.form.getlist("paths[]")
    if not paths:
        raise BadRequest('Missing "paths[]"')

    document_data = docai.process_sample(
        sample_name,
        SAMPLES_ROOT,
        paths,
        PROJECT_ID,
        processor_name,
    )

    return analysis_request(document_data)


@app.post("/api/analysis/processor/<string:processor_info>")
@api_post_request
def processor_analysis(processor_info: str):
    blobs = request.files.getlist("blobs[]")
    if not blobs:
        raise BadRequest('Missing "blobs[]"')

    documents = [(BytesIO(blob.read()), blob.mimetype) for blob in blobs]
    location, processor_id = processors.decode_processor_info(processor_info)
    document_data = docai.process_documents(
        documents,
        PROJECT_ID,
        location,
        processor_id,
    )

    return analysis_request(document_data)


@app.post("/api/document/render")
@api_post_request
def render_document():
    document_json = request.form.get("document_json", "")
    if not document_json:
        raise BadRequest('Missing "document_json"')
    options_json = request.form.get("options_json", "")
    if not options_json:
        raise BadRequest('Missing "options_json"')

    image_io, mimetype = render.render(document_json, options_json)

    return send_file(image_io, mimetype)


@app.get("/admin/processors/setup")
def setup_processors():
    docai.setup_processors(PROJECT_ID)
    return "setup_processors: done (see logs)\n"


def init_dev_env():
    # Run "python main.py" and open http://localhost:8080
    logging.getLogger().setLevel(logging.DEBUG)
    app.run(host="localhost", port=8080, debug=True)


def init_prod_env():
    from google.cloud.logging import Client

    Client().setup_logging()


if __name__ == "__main__":
    init_dev_env()
else:
    init_prod_env()
