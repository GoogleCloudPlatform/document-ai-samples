# Purpose and Description

The objective of the tooling is to efficiently integrate the output of one AI processor (proto) with another. This integration results in a comprehensive final output that reflects the combined capabilities of both parsers. Technically, this process involves sending the document proto object from one parser to the next.

## Input Details

* **PROJECT_ID :**  Google Cloud Project ID for the first processor.
* **LOCATION :**  Google Cloud project location for the first processor.
* **PROCESSOR_ID :**  Processor ID from the first processor.
* **MIME_TYPE :**   The MIME type for the files to be processed.
* **PROJECT_ID_2 :** Google Cloud Project ID for the second processor.
* **LOCATION_2 :**  Google Cloud project location for the second processor.
* **PROCESSOR_ID_2 :**  Processor ID from the second processor.
* **input_path :**  The path to the input PDF files.
* **output_path1 :**  The path for output from the first parser.
* **output_path2 :**  The path for output from the second parser.

## Output Details

The jsons will be stored in respective output folders.