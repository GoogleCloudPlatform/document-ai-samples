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
import io
import os
import pathlib
import typing

import flask
import google.auth

import docai

app = flask.Flask(__name__, static_url_path="")
samples_path = pathlib.Path("samples")


def get_project_id():
    _, project_id = google.auth.default()
    return project_id


@app.get("/")
def index():
    return flask.send_from_directory(str(app.static_folder), "index.html", etag=ETAG)


@app.get("/<filename>")
def static_file(filename):
    return flask.send_from_directory(str(app.static_folder), filename, etag=ETAG)


@app.get("/api/samples")
def samples():
    def get_samples(
        parent_path: pathlib.Path = samples_path,
        rel_dir: str = "",
    ) -> typing.Iterator[tuple[str, list[str]]]:
        paged_samples = []
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
    samples = dict(get_samples())

    # Note: jsonify sorts dictionaries by key by default
    return flask.jsonify(samples=samples)


@app.get("/api/samples/<path:file_path>")
def sample_file(file_path: str):
    return flask.send_from_directory(samples_path, file_path, etag=ETAG)


@app.get("/api/project")
def project():
    project_id = get_project_id()

    return flask.jsonify(project=project_id)


@app.get("/api/processors/locations")
def processors_locations():
    locations = docai.processors_locations()

    return flask.jsonify(locations=locations)


@app.get("/api/processors/<project_id>/<api_location>")
def id_processors(project_id: str, api_location: str):
    processors = docai.frontend_id_processors(project_id, api_location)

    return flask.jsonify(processors=processors)


@app.get("/api/processor/fields/<proc_info>")
def processor_fields(proc_info: str):
    processor = docai.processor_from_frontend_proc_info(proc_info)
    if processor is None:
        return f"Incorrect processor info: {proc_info}", 400

    fields = docai.get_processor_fields(processor)

    return flask.jsonify(fields=fields)


@app.post("/api/processor/analysis/<proc_info>")
def processor_analysis(proc_info: str):
    processor = docai.processor_from_frontend_proc_info(proc_info)
    if processor is None:
        return f"Incorrect processor info: {proc_info}", 400
    photos = flask.request.files.getlist("photos[]")
    if not photos:
        return 'Missing "photos[]" image(s)', 400

    files = [(io.BytesIO(p.read()), p.mimetype) for p in photos]
    document = docai.process_files(files, processor)
    analysis = docai.id_data_from_document(document)

    return flask.jsonify(analysis=analysis)


@app.get("/admin/processors/check")
def check_processors():
    project_id = get_project_id()
    docai.check_processors(project_id)

    return "check_processors: done (see logs)\n"


# Web apps deployed in a Buildpacks image have their source file timestamps zeroed
BUILDPACKS_CONTAINER_TIMESTAMP = "Tue, 01 Jan 1980 00:00:01 GMT"
# Enable ETag caching on static files deployed in Buildpacks images
IMAGE_VERSION = os.environ.get("K_REVISION", "")  # Cloud Run
if not IMAGE_VERSION:
    IMAGE_VERSION = os.environ.get("GAE_VERSION", "")  # App Engine
ETAG = IMAGE_VERSION if IMAGE_VERSION else True


@app.before_request
def before_request():
    environ = flask.request.environ
    if environ.get("HTTP_IF_MODIFIED_SINCE", "") == BUILDPACKS_CONTAINER_TIMESTAMP:
        # Fix caching issue with incorrect 304 responses that occur if the browser
        # previously received a wrong "Last-Modified" response
        del environ["HTTP_IF_MODIFIED_SINCE"]


@app.after_request
def after_request(response):
    if response.headers.get("Last-Modified", "") == BUILDPACKS_CONTAINER_TIMESTAMP:
        # The modification time is actually unknown
        response.headers.remove("Last-Modified")

    return response


if __name__ == "__main__":
    # Dev only: run "python main.py" (3.9+) and open http://localhost:8080
    os.environ["FLASK_ENV"] = "development"
    app.run(host="localhost", port=8080, debug=True)
else:
    # Prod only: cache static resources
    app.send_file_max_age_default = 3600  # 1 hour
