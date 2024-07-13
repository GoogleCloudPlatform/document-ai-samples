# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import re
from typing import Tuple, Optional, List
from google.cloud.documentai_toolbox import document
from google.cloud import documentai_v1 as documentai
from config import get_parser_by_name
from logging_handler import Logger

logger = Logger.get_logger(__file__)


def get_docai_input(processor_name: str) -> \
    Tuple[Optional[documentai.types.processor.Processor], Optional[documentai.DocumentProcessorServiceClient]]:
  """
  Retrieves the Document AI processor and client based on the processor name.

  Args:
      processor_name (str): The name of the processor.

  Returns:
      Tuple[Optional[documentai.types.processor.Processor], Optional[documentai.DocumentProcessorServiceClient]]:
      A tuple containing the processor and the Document Processor Service client.
  """
  parser_details = get_parser_by_name(processor_name)

  if not parser_details:
    logger.error(f"Parser {processor_name} not defined in config")
    return None, None

  processor_path = parser_details["processor_id"]
  location = parser_details.get("location", get_processor_location(processor_path))
  if not location:
    logger.error(f"Unidentified location for parser {processor_path}")
    return None, None

  opts = {"api_endpoint": f"{location}-documentai.googleapis.com"}

  dai_client = documentai.DocumentProcessorServiceClient(client_options=opts)
  processor = dai_client.get_processor(name=processor_path)

  logger.info(f"get_docai_input - processor={processor.name}, {processor.type_}")
  return processor, dai_client


def get_processor_location(processor_path: str) -> Optional[str]:
  """
  Extracts the location from the processor path.

  Args:
      processor_path (str): The processor path.

  Returns:
      Optional[str]: The location extracted from the processor path.
  """
  match = re.match(r'projects/(.+)/locations/(.+)/processors', processor_path)
  if match and len(match.groups()) >= 2:
    return match.group(2)
  return None


# TODO(developer): Uncomment these variables before running the sample.
# Given a local document.proto or sharded document.proto from a splitter/classifier in path
# document_path = "path/to/local/document.json"
# pdf_path = "path/to/local/document.pdf"
# output_path = "resources/output/"


def split_pdf_document(document_path: str, pdf_path: str, output_path: str) -> List[str]:
  try:
    wrapped_document = document.Document.from_document_path(document_path=document_path)
    output_files = wrapped_document.split_pdf(
      pdf_path=pdf_path, output_path=output_path
    )

    logger.info(f"Document {pdf_path} successfully split into {', '.join(output_files)}")
    return output_files
  except Exception as e:
    logger.error(f"Error splitting PDF document: {e}")
    return []

