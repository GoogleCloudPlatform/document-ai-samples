**Doc AI Incubator team**

Incubator team supports Doc AI clients in providing assistance on bugs,technical guidance and solutions based on the business needs.
GCP Doc AI experienced team members also suggests the best practices to get best out of the product for the given business case.

**Tools**
This Folder will have various documents and code snippets which is made for the benefit of Doc AI users.

  
1.  **File name:** DocAI PAI Best Practices Guide v1.0 - External.pdf
   
   This document will have the best practices of using Doc AI to get the better performance for your business needs.
Based on the experience of the team members, best practices for various processors and guide to improve the performance and few sample code snippets which helps to trouble shoot the issues .

2. **File name:** Doc AI Key_Value Entity Conversion (External).pdf

   This Document will guide to convert the  Key value pairs from the form parser output to the entities.

    Input :  Form parser output in a GCS folder
             Entity name and corresponding synonyms to be considered as keys (to check in form parser)
             GCS output folder
  
    Expected output:
       updated Json will be uploaded to GCS output folder provided with new entities updated in the jsons.

3. **File name:** DocAI - Script for Removing Empty Bounding Boxes (External).pdf

   This Document will help to remove the entities which are have empty bounding boxes (without any info in the mentiontext of the entity)

   Input :   Parsed json in a GCS folder
             GCS output folder to upload the updated jsons
  
   Expected output:
       Updated Json files with removing the entities with empty bounding boxes are uploaded into GCS output folder.


4. **File name:** Child Entity Tag Using Header Keyword (External).pdf
   
   This Document will guide us to find the line item entities based on the header key words provided

   Input :   Parsed json in a GCS folder
             Header keys with matching entity names
             GCS output folder to upload the updated jsons
  
   Expected output:
       The updated json will have the line item entities added based on finding of header keywords given as input .
       Gcs output folder will have the updated jsons.

5. **File name:** HITL Visualization Tool (External).pdf
   
   This Document uses HITL updated Json and will Visualize the document with HITL updated entities (bounding boxes) and other entities    with colour variation

   Input :   HITL Parsed jsons in a GCS folder
             
  
   Expected output:
       Excel file with image of document appended with bounding boxes for the entities updated in HITL and other entities with colour         variation and also a dot diagram which visualizes parent to child entity relation.
   
6. **File name:** HITL REJECTED DOCUMENTS TRACKING [External].pdf
   
   This Document gives the HITL rejected documents with a reason for rejection in csv file and also saves the rejected documents in a GCS folder given

   Input :  LRO numbers in list
             GCS folder to save the rejected documents             
  
   Expected output:
       Csv file which has document name and reason for rejection and files saved in GCS path

7. **File name:** PRE - POST HITL PARSER AND OCR ISSUE IDENTIFIER (External).pdf
   
   This Document guides to find out the Parser performance and OCR issues by comparing pre and post HITL jsons

   Input :  Pre HITL jsons in a GCS folder
            Post HITL jsons in a GCS folder            
  
   Expected output:
       A detailed comparision between pre and post HITL jsons with OCR and Parser issues highlighted and Entity wise issues are also provided in a seperate analysis folder.

8. **File name:** Document AI Parser Result Merger(External).pdf
   
   This Tool will combine various parser outputs into a single json file, the parser results provided can be of same document different parsers or different documents and different parsers.
   
   Input :  GCS folder which contains multiple parser output files to combine into single json           
            GCS folder to save the merged jsons
   Expected output:
       Merged parser output will be saved in the GCS folder.


   



   


   











