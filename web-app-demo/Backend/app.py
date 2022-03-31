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
from flask import Flask, request
from flask_restful import Api
from flask_cors import CORS  # comment this on deployment

import google.auth

from api.helper import process_document, store_file,populate_list_source

_, project_id = google.auth.default()
LOCATION = 'us'  # Format is 'us' or 'eu'

processor_id_by_processor_type = {}

app = Flask(__name__, static_url_path='', static_folder='')

CORS(app, support_credentials=True)
api = Api(app)


@app.route('/api/init', methods=['GET'])
def populate_list():
    """ Gets all available processors that are in the specified GCP project """
    return populate_list_source(project_id,LOCATION,processor_id_by_processor_type)


@app.route('/api/docai', methods=['POST'])
def get_document():
    """ Calls process_document and returns document proto """
    directory = 'api/test_docs'
    for file in os.listdir(directory):
        os.remove(os.path.join(directory, file))

    processor_type = request.form['fileProcessorType']

    file = request.files['file']
    file_type = file.content_type

    try:
        _destination = store_file(file)
    except Exception as err: # pylint: disable=W0703
        return {
            'resultStatus': 'ERROR',
            'errorMessage': str(err),
        }, 400

    process_document_request = {
        'project_id': project_id,
        'location': LOCATION,
        'processor_id': processor_id_by_processor_type[processor_type],
        'file_path': _destination,
        'processor_type': processor_type,
        'file_type': file_type
    }

    return process_document(process_document_request)


@app.route('/api/processor/list', methods=['GET'])
def get_list():
    """ Returns list of available processors """

    processor_list = list(processor_id_by_processor_type.keys())
    return {
        'resultStatus': 'SUCCESS',
        'processor_list': processor_list
    }
