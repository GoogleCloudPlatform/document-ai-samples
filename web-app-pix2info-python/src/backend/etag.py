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
import os

from flask import current_app
from flask import request
from flask.wrappers import Response

# Flask cache management for static files deployed in Buildpacks images

# Environment variables identifying a deployed version:
# - Cloud Run:  "K_REVISION"
# - App Engine: "GAE_VERSION"
IMAGE_VERSION = os.environ.get("K_REVISION", "") or os.environ.get("GAE_VERSION", "")
ETAG = IMAGE_VERSION or True

# Buildpacks zeroes out source file timestamps (for reproducibility purposes)
# See https://buildpacks.io/docs/features/reproducibility/#consequences-and-caveats
BUILDPACKS_IMAGE_TIMESTAMP = "Tue, 01 Jan 1980 00:00:01 GMT"


@current_app.after_request
def after_request(response: Response) -> Response:
    """Remove modification time when it is actually unknown."""
    if response.headers.get("Last-Modified", "") == BUILDPACKS_IMAGE_TIMESTAMP:
        response.headers.remove("Last-Modified")

    return response


@current_app.before_request
def before_request():
    """Fix caching issue with potential incorrect 304 responses."""
    if request.environ.get("HTTP_IF_MODIFIED_SINCE", "") == BUILDPACKS_IMAGE_TIMESTAMP:
        # The browser received a wrong "Last-Modified" response in a previous deployment
        del request.environ["HTTP_IF_MODIFIED_SINCE"]
