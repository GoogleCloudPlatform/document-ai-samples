# Purpose and Description

The labeled documents that are exported from a Document AI processor are saved in individual parent folders.
The purpose of the python code is used to generate a CSV file that maps the labeled documents with its parent folder name.
The first column of the generated CSV file contains the name of the parent folder, while the second column lists the files present within that parent folder.

## Input Details

* **project_id** : provide the project ID.
* **bucket_name** : provide the name of the bucket.
* **folder_name** :  provide the name of the folder path without prefixing the bucket name.

## Output Details

The above code generates a CSV file containing the name of the parent folder, while the second column lists the files present within that parent folder.