# Introduction
Our primary objective is to seamlessly automate the process of pinpointing documents that underperform, in order to facilitate their uptraining. A document's performance is quantified based on its count of missed crucial fields. This script operates according to the following specifications:

## Input Specifications
**Labeled Document Bucket:** The source containing labeled documents.

**Destination Bucket for Underperformers:** Where the poorly performing documents will be placed.

**Project and Processor Details:** Needed to invoke the desired processor. This includes the project ID, processor ID, and its version.

**Critical Fields List:** The script should first confirm that the names of these fields align with the schema. Discrepancies result in errors, prompting an update to the critical fields' input for congruence with the schema.

**Performance Threshold:** Determines when a document is deemed underperforming and should be transferred to the designated bucket.

## Numerical Substring Matching Criterion
**Processor-driven Document Evaluation:** The script processes documents using a designated processor. It identifies underperformers by assessing each document's critical fields against the Ground Truth (GT).

**optional Numerical Substring Matching:** Can be activated per entity. If this feature is on, as long as the numerical subset is accurate, the processor doesn't mark it as an oversight. For instance, if GT shows “ID 5123” and the prediction is “5123”, it isn't considered an error. The script acknowledges it as correct as long as the substring with the right numerical digits is detected.

## Logic for Relocating Underperforming Documents Based on Thresholds
**Output of Most Underperforming Documents:** The script outputs the worst-performing documents based on a custom-defined threshold. For example, documents that incorrectly identify over 50% of crucial fields are included in the output. The script can also recognize and process integer values; e.g., any document missing more than 5 crucial fields will be sent to the output bucket.
## Summary & Statistics of Output
**Missed Field List:** The script outputs a detailed list, either in sheets or CSV format, specifying misses in the critical fields for each document that's been transferred to the output bucket.