# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" Backend API that handles DocAI API calls """
import os
from typing import Dict

from api.helper import populate_list_source
from api.helper import process_document
from api.helper import store_file
from flask import Flask
from flask import jsonify
from flask import request
from flask_cors import CORS  # comment this on deployment
from flask_restful import Api
import google.auth

_, project_id = google.auth.default()
LOCATION = "us"  # Format is 'us' or 'eu'

processor_id_by_processor_type: Dict[str, str] = {}

app = Flask(__name__, static_url_path="", static_folder="")

CORS(app)
api = Api(app)


@app.route("/api/init", methods=["GET"])
def populate_list():
    """Gets all available processors that are in the specified GCP project"""

    populate_list_source(project_id, LOCATION, processor_id_by_processor_type)
    return jsonify(
        {
            "resultStatus": "SUCCESS",
        }
    )


@app.route("/api/docai", methods=["POST"])
def get_document():
    """Calls process_document and returns document proto"""

    directory = "api/test_docs"
    for file in os.listdir(directory):
        os.remove(os.path.join(directory, file))

    processor_type = request.form["fileProcessorType"]

    populate_list_source(project_id, LOCATION, processor_id_by_processor_type)

    processor_id = processor_id_by_processor_type.get(processor_type)
    print(processor_id)

    file = request.files["file"]
    file_type = file.content_type

    try:
        _destination = store_file(file)
    except Exception as err:  # pylint: disable=W0703
        return {
            "resultStatus": "ERROR",
            "errorMessage": str(err),
        }, 400

    process_document_request = {
        "project_id": project_id,
        "location": LOCATION,
        "file_path": _destination,
        "file_type": file_type,
        "processor_id": processor_id,
    }

    return process_document(process_document_request)


@app.route("/api/processor/list", methods=["GET"])
def get_list():
    """Returns list of available processors"""

    processor_list = list(processor_id_by_processor_type.keys())
    response = jsonify({"resultStatus": "SUCCESS", "processor_list": processor_list})

    return response


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
