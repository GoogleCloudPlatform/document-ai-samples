# Purpose of the Script

This tool is specifically designed to compare Pre-HITL JSON files (those parsed from a processor) and Post-HITL JSON files (those updated via HITL) sourced from a GCS bucket. The differences between the JSON files are presented in an Excel sheet, complete with images that feature bounding boxes.

## Output Details

The tool generates its output in Excel format. This Excel output delineates the entities that underwent HITL updates and those that remained unchanged. It also provides images of labeled documents captured both before and after HITL processing.

The Excel workbook produced is structured with a "Consolidated_Data" sheet summarizing all processed files, alongside individual comparison sheets for each file.

Notably, each generated Excel sheet will contain a batch of 20 files.

Within the Excel file, the following details are outlined:
- Pre-HITL text
- Post-HITL text
- An indication of whether the entity underwent an update during HITL, represented as 'YES' or 'NO'.

For any documents that either meet the requisite confidence threshold or lack a HITL output, the notation “NO POST HITL OUTPUT AVAILABLE” is appended at the conclusion of the consolidated sheets within the Excel workbook.

## Bounding Box Color Coding in Images

The tool utilizes color-coded bounding boxes in the output images to represent specific data:
- **Blue Bounding Box:** Represents entities found in the Pre-HITL JSON.
- **Red Bounding Box:** Denotes entities that were updated during the HITL process.
- **Green Bounding Box:** Indicates entities deleted during the HITL process. Specifically, these are entities originally detected by the parser but removed during HITL.

