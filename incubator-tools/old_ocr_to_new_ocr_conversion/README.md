# Purpose and Description

* The main purpose of this tool is to reprocess a provided set of old OCR-labeled Json with the new OCR engine, ensuring the entities stay consistent.  
* The output of the tool is a new OCR JSON file that replicates the entities present in the original OCR data. The tool ensures that the entities identified by the new OCR Engine are mapped appropriately to their corresponding text and page layout information in the new OCR data. 

**NOTE**: 
* The tool assumes that the bounding-box was drawn accurately in the last labeling, 
* Sometimes if the New OCR picked some noise (symbols) then those noise might come in the mentionText.
* A Human Review is required to validate the changes.


# Input Details


* **gcs_input_path**: GCS Storage name. It should contain DocAI processed output json files. This bucket is used for processing input files and saving output files in the folders.
* **gcs_output_path**: GCS URI of the folder, where the dataset is exported from the processor.
* **offset**: To expand the existing bounding box to include all the tokens corresponding to the entities, it can be adjusted to an optimal value. By Default it is 0.005.
* **project_number**:  Project Number
* **Processor_id**: Processor ID To Call the new Processor with new OCR
* **processor_version** :Processor version of the processor 

# Output Details

The converted JSON file are stored in the output directory.
