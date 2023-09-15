**Doc AI Incubator team**

Incubator team supports Doc AI clients in providing assistance on bugs,technical guidance and solutions based on the business needs.
GCP Doc AI experienced team members also suggests the best practices to get best out of the product for the given business case.

**Tools**
This Folder will have various documents and code snippets which is made for the benefit of customer.

  
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



   











