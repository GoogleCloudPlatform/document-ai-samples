# Overview
This utility is tailored to process Form parser JSON files, which are initially parsed using a processor. These files, sourced from the GCS bucket, are transformed from a key/value structure into entities. Once transformed, the tool saves them back into the GCS bucket in JSON format.

## Configuration
To make the tool operational, configure the following input parameters:

**PROJECT_ID:** Input your GCP project ID. This is optional.

**bucket_name:** Specify the name of the bucket from where the files will be sourced.

**formparser_path:** Designate the folder containing JSON files parsed with the form parser.

**output_path:** Identify the folder where the processed JSON files will be saved.

**entity_synonyms_list:** This list is structured to map entities with their synonyms. Replace placeholders like "Entity_1", "Entity_2" with the actual entity names. Similarly, replace "Entity_1_synonyms_1", "Entity_1_synonyms_2", etc., with the related synonyms for the respective entities.

## Output
Once the tool completes its operation, the transformed JSON files will be saved in the GCS directory specified by the output_path variable.