# OCR with PDF Embedded Text

From [Release Notes](https://cloud.google.com/document-ai/docs/release-notes#December_19_2022)

The Document AI OCR Processor has the following new features:

- The OCR Processor now supports extracting embedded text from digital PDFs in public preview. A fallback to the optical OCR model is automatically triggered to extract text in the regions when the PDF being processed contains non-digital text. To opt into this feature, set [`process_options.ocr_config.enable_native_pdf_parsing=true`](https://cloud.google.com/document-ai/docs/reference/rest/v1beta3/ProcessOptions#OcrConfig) in your API request to the OCR Processor.

Known issues with the digital PDF feature of the Document AI OCR Processor:

- On a small number of documents, the word ordering within lines of text as reported by native text extraction might be wrong.
- On certain documents, invisible text embedded in a native PDF may be reported.
- On certain Japanese documents, currency symbols such as Yen might be incorrectly extracted as `/`.
- On certain documents, apostrophe symbols may be missing in word/line results.
- On certain documents, native text extraction might report different word/line results than those obtained by image-based OCR on an identical document.

## Sample Document

- A sample document has been provided that demonstrates how the results can vary by using embedded text instead of OCR detected text.
- [Declaration of Independence (Cursive)](DeclarationOfIndependence-Cursive.pdf)
  - This document is the text of The Declaration of Independence in a cursive script created in Google Docs.
  - Try this document with the sample code in [`main.py`](main.py) with `enable_native_pdf_parsing` set to `True` or `False` and compare the results.
  - [Example Diff](https://www.diffchecker.com/Z4QIzt3H/) (`enable_native_pdf_parsing` set to `True` and `False` respectively
