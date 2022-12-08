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

"""Flask Web Server"""

import os

from flask import Flask, render_template, request

from consts import (
    LOCATION,
    PROJECT_ID,
    SUPPORTED_TYPES,
    VALID_LANGUAGES,
)

from ekg_utils import search_public_kg

from google.api_core.exceptions import ResourceExhausted

from werkzeug.exceptions import HTTPException

app = Flask(__name__)

FORM_OPTIONS = {
    "language_list": VALID_LANGUAGES,
    "type_list": SUPPORTED_TYPES,
    "default_language": VALID_LANGUAGES[0],
}


@app.route("/", methods=["GET"])
def index() -> str:
    """
    Web Server, Homepage
    """

    return render_template("index.html", form_options=FORM_OPTIONS)


@app.route("/search_ekg", methods=["POST"])
def search_ekg() -> str:
    """
    Handle Search EKG Request
    """
    search_query = request.form.get("search_query", "")

    # Check if POST Request includes search query
    if not search_query:
        return render_template(
            "index.html",
            form_options=FORM_OPTIONS,
            message_error="No query provided",
        )

    languages = request.form.getlist("languages")
    types = request.form.getlist("types")

    entities, request_url, raw_request, raw_response = search_public_kg(
        project_id=PROJECT_ID,
        location=LOCATION,
        search_query=search_query,
        languages=languages,
        types=types,
    )

    return render_template(
        "index.html",
        form_options=FORM_OPTIONS,
        message_success=search_query,
        entities=entities,
        request_url=request_url,
        raw_request=raw_request,
        raw_response=raw_response,
    )


@app.errorhandler(Exception)
def handle_exception(ex: Exception):
    """
    Handle Application Exceptions
    """
    message_error = "An Unknown Error Occured"

    # Pass through HTTP errors
    if isinstance(ex, HTTPException):
        message_error = ex.get_description()
    elif isinstance(ex, ResourceExhausted):
        message_error = ex.message
    else:
        message_error = str(ex)

    return render_template(
        "index.html",
        form_options=FORM_OPTIONS,
        message_error=message_error,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
