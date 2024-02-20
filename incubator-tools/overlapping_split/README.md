# Purpose and Description
This tool uses exported labeled json to separate a pair of entities that are overlapped due to labeling into two individual entities.

## Prerequisites

1. Vertex AI Notebook
2. Parsed json files in GCS Folder.
3. Output folder to upload the updated json files.

## Step by Step procedure

### 1. Input details
input_path : GCS Path for input json files<br>
output_path: GCS Path for output json files<br>
list_of_pair_of_entities: [('customer_account_name','ship_to_address')]

<div><i><b>Note:</b> List of pairs of entities that need to be splitted. Also, the entity name should be mentioned like this (small_entity,large_entity)</i><div>


### 2. OutputThe output json after execution of the code have individual entities
<img src="./Images/overlapping_split_output_1.png" width=800 height=400 alt="Overlapping entity split output">

