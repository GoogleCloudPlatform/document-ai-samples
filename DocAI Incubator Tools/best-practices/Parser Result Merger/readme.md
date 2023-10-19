## Introduction
The Document AI Parser Result Merger is a utility developed in Python to seamlessly merge multiple resultant JSON files produced by Document AI processors. Given that documents typically span multiple pages, this tool provides two distinct use cases for merging these JSON files. This README elaborates on the tool's functionality and its operational prerequisites.

## Use Cases
**Case 1:** Merging JSON Results from Different Documents (Default)
This scenario applies when merging JSON outputs stemming from distinct documents.
To activate this mode, set the flag to 1.
**Case 2:** Merging JSON Results from the Same Document (Enhanced Functionality)
This scenario is pertinent when integrating multiple JSON outputs that are all derived from a single document.
To initiate this mode, set the flag to 2.
Workflow Overview
### The tool's workflow is structured as follows:

**Input GCP Bucket:** This container holds the multitude of JSON files that are targeted for merging.

**Processing with Python Script:** This script is designed to accept and process the input JSON files. It also facilitates the user's transition between the default (Case 1) and enhanced (Case 2) modes, based on the modes detailed above.

**Output GCP Bucket:** The unified, merged JSON file is saved into this GCP bucket post-processing.

## Outputs
### CASE 1 Output:
Considering that three JSON files emerge from varying documents (regardless of whether the parser is identical):

In this mode, the cumulative count of both Pages and Entities grows proportionately with the count in the input files. The Text values from each file are integrated and presented as a singular value within the Text key of the output JSON.

### CASE 2 Output:
Assuming that the trio of JSON files originate from one document but differ in parser results:

In this mode, the Pages count remains constant. However, there's an augmentation in the Entities count as the input JSON files merge. For instance, if every individual JSON contains 2 pages and 21 entities, the consolidated output JSON will display 2 pages but a total of 63 entities.