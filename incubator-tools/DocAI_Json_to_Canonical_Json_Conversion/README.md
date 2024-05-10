# Purpose and Description

A parsed, unstructured document is represented by JSON that describes the unstructured document using a sequence of text, table, and list blocks. You import canonical JSON files with your parsed unstructured document data in the same way that you import other types of unstructured documents, such as PDFs.

When this feature is turned on, whenever a JSON file is uploaded and identified by either an application/json MIME type or a .JSON extension, it is treated as a parsed document.

## Input Details

* **GCS_INPUT_PATH** : GCS path for input files. It should contain DocAI processed output json files and also the pdfs which got parsed by the processor with the same name as json files.

The input bucket should contain two folders. One should be processor_output and the other should be pdfs folder.

## Output Details

Document AI json after conversion to Canonical json and store the files to output folder inside the GCS_INPUT_PATH folder. Each page text will get store inside each text block with their respective page number.