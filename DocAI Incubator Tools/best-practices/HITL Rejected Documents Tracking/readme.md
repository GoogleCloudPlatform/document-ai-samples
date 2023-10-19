## Overview

This Script is to oversee documents that the HITL system has declined. By accepting a set of Long Running Operation (LRO) IDs, it offers a glimpse into the documents that HITL has rejected based on those LROs. In addition to this, the Script also modifies and relocates processed JSON data to a predetermined GCS directory, now inclusive of a 'HITL_Status' entity.

## Input Guidelines
**LRO List:** This is essentially a list of IDs that are generated once batch processing is completed.

**GCS HITL Rejected Path:** This is the designated directory within GCS where you'd want your JSON data stored. Ensure that this path concludes with a forward slash ('/').

**Project ID:** This refers to the unique identifier of your project.

**Location:** This is the geographical region or locale where the processing takes place, such as 'us' or 'eu'.

## Output Details
Post-execution, the utility delivers outcomes in two distinct formats:

**CSV Format:** A file named HITL_Status_Update.csv will be generated. This file will contain details like the file names, their HITL status, and, if applicable, reasons for their rejection by HITL.

**JSON Format:** The processed JSON will now have an added entity, 'HITL_Status', and will be relocated to the previously specified GCS directory.