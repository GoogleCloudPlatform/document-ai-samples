# (WIP) Scientific Paper Summarization using Document AI and Vertex AI

## Training Data

[ScisummNet - Scientific Article Summarization Dataset](https://cs.stanford.edu/~myasu/projects/scisumm_net/)

- Google Cloud Storage Bucket: `gs://cloud-samples-data/documentai/ScisummNet`
  - `pdf` - Original PDF files of papers from [ACL Anthology](https://aclanthology.org)
  - `summary_txt` - Human-written summaries of papers
  - `json` - Contains [Document.json](https://cloud.google.com/document-ai/docs/reference/rest/v1/Document) files processed by the [Document AI OCR Processor](https://cloud.google.com/document-ai/docs/processors-list#processor_doc-ocr)
  - `full_txt` - Contains Full OCR-Extracted Text from each Document extracted from Document.json files