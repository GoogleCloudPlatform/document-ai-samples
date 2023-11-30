# Utilities for Google Cloud Storage Operations

The `utilities.py` script offers a suite of utility functions designed to simplify and streamline operations associated with Google Cloud Storage (GCS) and Google Cloud's DocumentAI.

## Features

1. **Retrieving File Names**: Quickly fetch a list of files from a given GCS path.
2. **Bucket Management**: Effortlessly check for the existence of a GCS bucket, create one if it doesn't exist, or delete it when done.
3. **File Listings**: Retrieve a list of all files (blobs) within a specified GCS bucket.
4. **File Matching**: Compare files between two GCS buckets to identify similar filenames.
5. **Document Conversion**: Download a file from GCS and convert it into a DocumentAI Document proto.
6. **Blob Operations**: Easily copy blobs (files or objects) from one GCS bucket to another and several other functions.
7. **Upload Blobs**: To upload json files to GCS Path

## Dependencies

The functions mainly rely on Google Cloud Python client libraries such as:
- `google.cloud.storage`
- `google.cloud.documentai_v1beta3`

To utilize these utilities, ensure the appropriate packages are installed and you have set up authentication with GCS.

## Usage

Download incubator-tools utilities module into your script of notebook:

```python
!wget https://raw.githubusercontent.com/GoogleCloudPlatform/document-ai-samples/main/incubator-tools/best-practices/utilities/utilities.py
```

To use the functions, simply import `utilities.py` into your script or notebook:

```python
import utilities
```

## Note
For detailed functionality and parameters of each function, kindly refer to the docstrings within utilities.py.
