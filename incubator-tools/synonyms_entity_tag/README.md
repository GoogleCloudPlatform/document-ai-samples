# Purpose and Description
This tool uses parsed json files and a dictionary with key as entity names and values as synonyms for which the entity has to be tagged.
New entities added to the json.

Approach: The values of the dictionary are searched in the OCR text and tagged with entity name based on key.

## Input Details

* **project_id**: It is the project id of the project.
* **gcs_input_path**: GCS Storage name. It should contain DocAI processed output json files. This bucket is used for processing input files and saving output files in the folders.
* **gcs_output_path**: GCS URI of the folder, where the output is stored.
* **synonyms_entities**: A dictionary with key as entity names and values as synonyms for which the entity has to be tagged.

## Output Details

The output jsons files will be stored in the given output directory.