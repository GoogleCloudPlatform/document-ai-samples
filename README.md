# Google Cloud Document AI Samples

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![GitHub Super-Linter](https://github.com/GoogleCloudPlatform/document-ai-samples/workflows/Lint%20Code%20Base/badge.svg)](https://github.com/marketplace/actions/super-linter)
![Document AI](https://storage.googleapis.com/gweb-cloudblog-publish/images/gcp_docai_platform.1000064920000870.max-2000x2000.jpg)

Welcome to the Google Cloud [Document AI](https://cloud.google.com/document-ai) sample repository.

## Overview

The repository contains samples and [Community Samples](https://github.com/GoogleCloudPlatform/document-ai-samples/tree/main/community) that demonstrate how to analyze, classify and search documents using Google Cloud Document AI.

## Samples

* [PDF Splitter Sample](https://github.com/GoogleCloudPlatform/document-ai-samples/tree/main/pdf-splitter-python): This project uses the Document AI API to split PDF documents.
* [Web App Demo](https://github.com/GoogleCloudPlatform/document-ai-samples/tree/main/web-app-demo): This project is a fullstack application that uses Document AI to process different types of documents. This application currently supports Form, Invoice and OCR processors.
* [Tax Processing Pipeline](tax-processing-pipeline-python/): This project uses the Document AI API to classify, parse, and calculate a tax form using multiple document types.
* [Fraud Detection](fraud-detection-python/): This project uses the Document AI Invoice Parser with EKG and Google Maps to store document Entities in BigQuery.

### Test Document Files

If you need Document Files to run the samples, you can access them from this publicly-accessible [Google Cloud Storage Bucket](https://cloud.google.com/storage/docs/downloading-objects).

`gs://cloud-samples-data/documentai/`

The directory is organized by solution and document type, you can see the folder structure listed here.

```console
documentai/
├── codelabs
│   ├── form-parser
│   │   └── intake-form.pdf
│   ├── hitl
│   │   ├── expense-claim.pdf
│   │   └── hitl-instructions.pdf
│   ├── ocr
│   │   ├── Winnie_the_Pooh_3_Pages.pdf
│   │   └── Winnie_the_Pooh.pdf
│   └── specialized-processors
│       ├── google_invoice.pdf
│       ├── lending_multi_document.pdf
│       ├── procurement_multi_document.pdf
│       └── W9.pdf
├── Contract DocAI
│   ├── CymbalContract.pdf
│   └── Healthcare licensing agreement.pdf
├── General Processors
│   ├── Document OCR (Optical Character Recognition)
│   │   ├── hello_world.pdf
│   │   ├── kafka.pdf
│   │   ├── Winnie_the_Pooh_3_Pages.pdf
│   │   └── Winnie_the_Pooh.pdf
│   ├── Document Splitter
│   │   └── multi-document.pdf
│   ├── Form Parser
│   │   ├── intake-form.pdf
│   │   ├── loan_form.pdf
│   │   ├── medical_lab_form.pdf
│   │   ├── NASADeclaration.jpg
│   │   ├── PDFTables.pdf
│   │   ├── PDFTables.tiff
│   │   ├── Table1.pdf
│   │   ├── Table1.tiff
│   │   ├── table_parsing_small.pdf
│   │   ├── Tables-2page.pdf
│   │   ├── tables-3page.pdf
│   │   ├── tables.pdf
│   │   └── tx_drivers_license(stained).pdf
│   └── Intelligent Document Quality Processor
│       └── texas_drivers_license(stained).pdf
├── Identity DocAI
│   ├── Driver's License (USA)
│   │   ├── Colorado_2016_Drivers License_AllAges_Default_Front_Fullres.jpg
│   │   ├── dl2.pdf
│   │   ├── dl3.jpeg
│   │   ├── dl3.pdf
│   │   └── dl.pdf
│   └── Passport (USA)
│       └── obama pp.pdf
├── Lending DocAI
│   ├── 1040 Parser
│   │   ├── 1040_blackwhite.pdf
│   │   ├── 1040Burnett.pdf
│   │   ├── 1040-kyle.pdf
│   │   ├── 1040.pdf
│   │   ├── 1040-rotated-coffeeStained.pdf
│   │   └── 2018 Form 1040-Hummell.pdf
│   ├── 1099-DIV Parser
│   │   └── 2020 Form 1099-DIV - Anastasia Hodges.pdf
│   ├── 1099-INT Parser
│   │   └── 2020 Form 1099-INT - Anastasia Hodges.pdf
│   ├── 1099-MISC Parser
│   │   ├── 0241-1099_misc-2018-ar-08.pdf
│   │   ├── 0242-1099_misc-2018-ar-08.pdf
│   │   ├── 0243-1099_misc-2018-ar-08.pdf
│   │   ├── 0244-1099_misc-2018-ar-08.pdf
│   │   ├── 0245-1099_misc-2018-ar-08.pdf
│   │   ├── 0401-1099_misc-2019-hw.pdf
│   │   ├── 0402-1099_misc-2019-hw.pdf
│   │   ├── 0403-1099_misc-2019-hw.pdf
│   │   ├── 0404-1099_misc-2019-hw.pdf
│   │   ├── 0405-1099_misc-2019-hw.pdf
│   │   ├── 0406-1099_misc-2019-hw.pdf
│   │   ├── 0407-1099_misc-2019-hw.pdf
│   │   ├── 0408-1099_misc-2019-hw.pdf
│   │   ├── 0409-1099_misc-2019-hw.pdf
│   │   ├── 0410-1099_misc-2019-hw.pdf
│   │   └── 2020 Form 1099-MISC - Anastasia Hodges.pdf
│   ├── 1099-NEC Parser
│   │   └── 2020 Form 1099-NEC - Anastasia Hodges.pdf
│   ├── 1099-R Parser
│   │   └── 2020 Form 1099-R - Anastasia Hodges.pdf
│   ├── Bank Statement Parser
│   │   └── lending_bankstatement.pdf
│   ├── Lending Document Splitter & Classifier
│   │   ├── Combined_LDAI_Classifier-1.pdf
│   │   ├── Combined_LDAI_Classifier-2.pdf
│   │   ├── Combined_LDAI_Classifier-3.pdf
│   │   ├── Combined_LDAI_Classifier.pdf
│   │   └── lending_multi_document.pdf
│   └── Pay Slip Parser
│       ├── 0001-paystub-walmart-hv8.pdf
│       ├── 0002-paystub-walmart-hv8.pdf
│       ├── 0003-paystub-walmart-hv8.pdf
│       ├── 0004-paystub-walmart-hv8.pdf
│       ├── 0005-paystub-walmart-hv8.pdf
│       ├── 0006-paystub-walmart-ar8.pdf
│       ├── 0007-paystub-walmart-ar8.pdf
│       ├── 0008-paystub-walmart-ar8.pdf
│       ├── 0009-paystub-walmart-ar8.pdf
│       ├── 0010-paystub-walmart-ar8.pdf
│       ├── GoogleNext_PayStub.pdf
│       └── paystub.pdf
└── Procurement DocAI
    ├── Expense Parser
    │   ├── AngelinasReceipt.tiff
    │   ├── GroceryReceipt.pdf
    │   ├── office-depot-receipt2.png
    │   ├── office-depot-receipt.pdf
    │   ├── office-depot-redacted.png.pdf
    │   ├── Starbucks.tiff
    │   └── time-out market.jpg
    ├── Invoice Parser
    │   ├── 244-en-invoice-commercial-ty.pdf
    │   ├── 259-en-invoice-commercial-ty.pdf
    │   ├── 279-en-invoice-commercial-ty.pdf
    │   ├── 280-en-invoice-commercial-ty.pdf
    │   ├── 281-en-invoice-commercial-ty.pdf
    │   ├── 282-en-invoice-commercial-ty.pdf
    │   ├── 283-en-invoice-commercial-ty.pdf
    │   ├── baking_technologies_invoice.pdf
    │   ├── generic_invoice.pdf
    │   ├── google_invoice.pdf
    │   ├── google_invoice.png
    │   ├── invoice_multi_page_rotated.pdf
    │   ├── invoices_en_invoice.pdf
    │   ├── PMI-471766.pdf
    │   ├── PMI-471767.pdf
    │   ├── PMI-471991.pdf
    │   ├── PMI-472016.pdf
    │   ├── PMI-473733.pdf
    │   ├── PMI-473789.pdf
    │   ├── PMI-474121.pdf
    │   ├── Stanford Plumbing & Heating.pdf
    │   └── thai invoice.pdf
    ├── Procurement Document Splitter & Classifier
    │   └── procurement_multi_document.pdf
    └── Utility Parser
        ├── 003-en-invoice-utility.pdf
        ├── 007-en-invoice-utility.pdf
        ├── sce_g-bill.pdf
        └── sce&g-bill.png
```

## Codelabs
<!-- markdownlint-disable MD033 -->
<img src="https://www.gstatic.com/devrel-devsite/prod/vc705ce9bd51279e80f03a51aec7c6eb1f05e56e75c958618655fc719098c9888/codelabs/images/lockup.svg" alt="Codelabs Logo" width="200"/>

* [Optical Character Recognition (OCR) with Document AI (Python)](https://codelabs.developers.google.com/codelabs/docai-ocr-python)
* [Form Parsing with Document AI (Python)](https://codelabs.developers.google.com/codelabs/docai-form-parser-v1-python)
* [Specialized Processors with Document AI (Python)](https://codelabs.developers.google.com/docai-specialized-processors)

## Community Samples

---
**Disclaimer:** Community samples are not officially maintained by Google.

---

* [PDF Annotator Sample](https://github.com/GoogleCloudPlatform/document-ai-samples/tree/main/community/pdf-annotator-python): This project uses the Document AI API to annotate PDF documents.

## Contributing

Contributions welcome! See the [Contributing Guide](https://github.com/GoogleCloudPlatform/document-ai-samples/blob/main/.github/CONTRIBUTING.md).

## Getting help

Please use the [issues page](https://github.com/GoogleCloudPlatform/document-ai-samples/issues) to provide feedback or submit a bug report.

## Disclaimer

This is not an officially supported Google product. The code in this repository is for demonstrative purposes only.
