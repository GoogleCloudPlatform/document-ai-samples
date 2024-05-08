# Document Schema Export/Import Guide

This guide provides instructions on how to export a schema from a processor to a spreadsheet (.xlsx extension) and how to import a schema from a spreadsheet to a processor. This process supports up to three levels of nesting.

## Prerequisites

- **Vertex AI Notebook** or **Google Colab** (use authentication if using Colab)
- Details of the processor to import the processor schema
- Permissions for Google Storage and Vertex AI Notebook

## Exporting a Document Schema to a Spreadsheet

### Input

- `project_id="xxxxxxxxxx"`: Project ID of the project
- `location="us"`: Location of the processor
- `processor_id="xxxxxxxxxxxxxxx"`: Processor ID from which the schema will be exported

### Output

The schema will be saved in a file named `Document_Schema_exported.xlsx`. The spreadsheet will have the following columns:

- **Name**: Entity type which can be a parent or child entity.
- **Value_type**: Data type of the entities; for parent items, this will be the same as the entity type. For final child types, this will be the data type.
- **Occurance_type**: Occurrence type of the respective entity.
- **Display_name**: Name of the parent entity for child entities. If the entity itself is the parent entity, then `display_name` will be empty.

## Importing Document Schema from a Spreadsheet

### Input

- `project_id="xxxxxxxxxx"`: Project ID of the project
- `new_location="us"`: Location of the processor
- `new_processor_id="xxxxxxxxxxxxxxx"`: Processor ID to which the schema will be imported
- `schema_xlsx_path="Document_Schema_exported.xlsx"`: Path to the schema file in .xlsx format

### Additional Steps

Add any entities in the .xlsx file to be added to the new processor.

### Note

Ensure the entities in the spreadsheet are not already in the schema of the processor to avoid issues.

### Output

The schema of the new processor will be updated as per the spreadsheet provided.
