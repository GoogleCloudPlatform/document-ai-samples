# Google Cloud Document AI Samples

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![GitHub Super-Linter](https://github.com/GoogleCloudPlatform/document-ai-samples/workflows/Lint%20Code%20Base/badge.svg)](https://github.com/marketplace/actions/super-linter)
![Document AI](https://storage.googleapis.com/gweb-cloudblog-publish/images/gcp_docai_platform.1000064920000870.max-2000x2000.jpg)

Welcome to the Google Cloud [Document AI](https://cloud.google.com/document-ai) sample repository.

## Overview

The repository contains samples and [Community Samples](https://github.com/GoogleCloudPlatform/document-ai-samples/tree/main/community) that demonstrate how to analyze, classify and search documents using Google Cloud Document AI.

## Samples

* [Document AI Warehouse Processing](document_ai_warehouse_processing_python/): This project demonstrates how to perform common actions on Document AI Warehouse through API.
* [BQ Connector](bq-connector/): This project uses the Document AI API to process a document, format the result and save it into a BigQuery table.
* [Filter HITL Language](filter-hitl-language/): This project uses the languages detected by Document AI (post-HITL) to sort the `Document.json` files into separate Cloud Storage buckets.
* [Fraud Detection](fraud-detection-python/): This project uses the Document AI Invoice Parser with EKG and Google Maps to store document Entities in BigQuery.
* [JSON Explorer](document-json-explorer/): A React Tool to explore the Document JSON Response.
* [Language Extraction](extract-languages/): This project uses the Document AI API to detect the languages in a multi-page document.
* [Paper Summarization](paper_summarization/): This project uses the Document AI API to summarize scientific articles.
* [PDF Splitter](pdf-splitter-python/): This project uses the Document AI API to split PDF documents.
* [SQL over Docs](sql-pdf-python/): This project shows how to run a BigQuery SQL and extract information from documents.
* [Tabular Data Extraction](extract-tables/): This project uses the Document AI API to extract tabular data from a document.
* [Tax Processing Pipeline](tax-processing-pipeline-python/): This project uses the Document AI API to classify, parse, and calculate a tax form using multiple document types.
* [Web App Demo](web-app-demo/): This project is a full-stack application that uses Document AI to process different types of documents. This application currently supports Form, Invoice and OCR processors.

### Samples not in this Repository

* https://github.com/GoogleCloudPlatform/documentai-sheets-plugin
* https://github.com/GoogleCloudPlatform/document-intake-accelerator

### Test Document Files

If you need Document Files to run the samples, you can access them from this publicly-accessible [Google Cloud Storage Bucket](https://cloud.google.com/storage/docs/downloading-objects).

`gs://cloud-samples-data/documentai/`

You can also view sample input/output files by processor on the [Sample Output](https://cloud.google.com/document-ai/docs/output) page of the documentation.

## Codelabs
<!-- markdownlint-disable MD033 -->
<img src="https://www.gstatic.com/devrel-devsite/prod/vc705ce9bd51279e80f03a51aec7c6eb1f05e56e75c958618655fc719098c9888/codelabs/images/lockup.svg" alt="Codelabs Logo" width="200"/>

* [Optical Character Recognition (OCR) with Document AI (Python)](https://codelabs.developers.google.com/codelabs/docai-ocr-python)
* [Form Parsing with Document AI (Python)](https://codelabs.developers.google.com/codelabs/docai-form-parser-v1-python)
* [Specialized Processors with Document AI (Python)](https://codelabs.developers.google.com/codelabs/docai-specialized-processors)
* [Managing Document AI processors (Python)](https://codelabs.developers.google.com/codelabs/cloud-documentai-manage-processors-python)

## Community Samples

---
**Disclaimer:** Community samples are not officially maintained by Google.

---

* [PDF Annotator Sample](community/pdf-annotator-python): This project uses the Document AI API to annotate PDF documents.

## Contributing

Contributions welcome! See the [Contributing Guide](https://github.com/GoogleCloudPlatform/document-ai-samples/blob/main/.github/CONTRIBUTING.md).

## Getting help

Please use the [issues page](https://github.com/GoogleCloudPlatform/document-ai-samples/issues) to provide feedback or submit a bug report.

## Disclaimer

This is not an officially supported Google product. The code in this repository is for demonstrative purposes only.
