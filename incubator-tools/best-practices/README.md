# Folders

* Key_Value_Pair_Entity_Conversion

This notebook will guide to convert the Key value pairs from the form parser output to the entities.

Input : Form parser output in a GCS folder Entity name and corresponding synonyms to be considered as keys (to check in form parser) GCS output folder
Expected output: updated Json will be uploaded to GCS output folder provided with new entities updated in the jsons.

* Removing_Empty_Bounding_Boxes

This notebook will help to remove the entities which are having empty bounding boxes (without any info in the mentiontext of the entity)

Input : Parsed json in a GCS folder GCS output folder to upload the updated jsons
Expected output: Updated Json files with removing the entities with empty bounding boxes are uploaded into GCS output folder.

* Child_Entity_Tag_Using_Header_Keyword

This notebook will guide us to find the line item entities based on the header key words provided

Input : Parsed json in a GCS folder Header keys with matching entity names GCS output folder to upload the updated jsons
Expected output: The updated json will have the line item entities added based on finding of header keywords given as input . Gcs output folder will have the updated jsons.

* Pre_and_Post_HITL_Visualization

This notebook uses HITL updated Json and will Visualize the document with HITL updated entities (bounding boxes) and other entities with colour variation

Input : HITL Parsed jsons in a GCS folder
Expected output: Excel file with image of document appended with bounding boxes for the entities updated in HITL and other entities with colour variation and also a dot diagram which visualizes parent to child entity relation.

* HITL_Rejected_Documents_Tracking

This notebook gives the HITL rejected documents with a reason for rejection in csv file and also saves the rejected documents in a GCS folder given

Input : LRO numbers in list GCS folder to save the rejected documents
Expected output: Csv file which has document name and reason for rejection and files saved in GCS path


* Document_AI_Parser_Result_Merger

This notebook will combine various parser outputs into a single json file, the parser results provided can be of same document different parsers or different documents and different parsers.

Input : GCS folder which contains multiple parser output files to combine into single json
Expected output: Merged parser output will be saved in the GCS folder.

* Pre_Post_HITL_Bounding_Box_Mismatch

This notebook identifies two primary issues: Parser and OCR discrepancies. The outcome of this tool is a summary JSON file detailing basic statistics and counts of the OCR and Parser issues for entities in each document, along with corresponding analysis in CSV files.

Input : Pre and Post HITL jsons in a GCS folder
Expected output: Result summary table is obtained with details parser and OCR issues for each file, including entity changes and bounding box mismatches after HITL processing. Additionally, a JSON file notes bounding box mismatches, OCR and Parser errors, and directs to the results table for every file processed.