# Apps Script & Google Drive Integration

This directory contains code in Google [Apps Script](https://developers.google.com/apps-script) for integration with Document AI.

1. Must setup [OAuth2 library for Apps Script](https://github.com/googleworkspace/apps-script-oauth2#setup) to run.

## `runOnlineProcessing()`

- Original Source: [googleworkspace/ml-integration-samples/apps-script/documentai/documentai.js](https://github.com/googleworkspace/ml-integration-samples/blob/master/apps-script/documentai/documentai.js)
- Downloads file from Google Drive and sends it to Document AI for [online processing](https://cloud.google.com/document-ai/docs/send-request#online-processor).

## `runCloudStorage()`

- Downloads file from Google Drive and Imports into Cloud Storage for later [batch processing](https://cloud.google.com/document-ai/docs/send-request#batch-process)
