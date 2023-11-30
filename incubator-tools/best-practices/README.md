# Folders

* Key_Value_Pair_Entity_Conversion

    This notebook will guide to convert the Key value pairs from the form parser output to the entities.

    <strong>Input</strong>: Form parser output in a GCS folder Entity name and corresponding synonyms to be considered as keys (to check in form parser) GCS output folder.<br/>
    <strong>Expected output</strong>: updated Json will be uploaded to GCS output folder provided with new entities updated in the jsons.

* Removing_Empty_Bounding_Boxes

    This notebook will help to remove the entities which are having empty bounding boxes (without any info in the mentiontext of the entity)

    <strong>Input</strong>: Parsed json in a GCS folder GCS output folder to upload the updated jsons.<br/>
    <strong>Expected output</strong>: Updated Json files with removing the entities with empty bounding boxes are uploaded into GCS output folder.

* Identifying_Poor_Performing_Docs

    This notebook uses Labeled jsons and parser details with critical fields as input and checks the performance of the processor with documentsand gives the documents which have discrepancies from the labeled jsons and entity wise discrepancies in a json format. This can be used to improve the performance of the processor after uptraining.

    <strong>Input</strong>: Labeled jsons and Parser details.<br/>
    <strong>Expected Output</strong>: Poor performing documents in a gcs folder provided

* Pre_and_Post_HITL_Visualization

    This notebook uses HITL updated Json and will Visualize the document with HITL updated entities (bounding boxes) and other entities with colour variation

    <strong>Input</strong>: HITL Parsed jsons in a GCS folder.<br/>
    <strong>Expected output</strong>: Excel file with image of document appended with bounding boxes for the entities updated in HITL and other entities with colour variation and also a dot diagram which visualizes parent to child entity relation.

* HITL_Rejected_Documents_Tracking

    This notebook gives the HITL rejected documents with a reason for rejection in csv file and also saves the rejected documents in a GCS folder given

    <strong>Input</strong>: LRO numbers in list GCS folder to save the rejected documents.<br/>
    <strong>Expected output</strong>: Csv file which has document name and reason for rejection and files saved in GCS path


* Document_AI_Parser_Result_Merger

    This notebook will combine various parser outputs into a single json file, the parser results provided can be of same document different parsers or different documents and different parsers.

    <strong>Input</strong>: GCS folder which contains multiple parser output files to combine into single json.<br/>
    <strong>Expected output</strong>: Merged parser output will be saved in the GCS folder.

* Pre_Post_HITL_Bounding_Box_Mismatch

    This notebook identifies two primary issues: Parser and OCR discrepancies. The outcome of this tool is a summary JSON file detailing basic statistics and counts of the OCR and Parser issues for entities in each document, along with corresponding analysis in CSV files.

    <strong>Input</strong>: Pre and Post HITL jsons in a GCS folder<br/>
    <strong>Expected output</strong>: Result summary table is obtained with details parser and OCR issues for each file, including entity changes and bounding box mismatches after HITL processing. Additionally, a JSON file notes bounding box mismatches, OCR and Parser errors, and directs to the results table for every file processed.