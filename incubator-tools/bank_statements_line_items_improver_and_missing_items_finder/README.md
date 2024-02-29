# Purpose and Description

The objective of the tool is to find the missing child items and group the correct child items into parent line items

## Input Details

* **Gcs_input_path** : GCS Input Path. It should contain DocAI processed output json files.
* **Gcs_output_path** : GCS Output Path. The updated jsons will be saved in output path.
* **project_id** : It should contains the project id of your current project.
* **parent_type** : Specify the parent entity type like table_item, line_item
* **Missing_items_flag**:  "True" if we need to find the missing child items , missing items step will be skipped if this value is other than True

## Output Details

The missing fields will be detected from the existing line items and grouped and updated json is saved in ouput path
