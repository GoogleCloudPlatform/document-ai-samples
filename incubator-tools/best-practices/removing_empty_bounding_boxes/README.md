# Purpose of the Script
This Python script are designed to streamline the labeling process of JSON files by identifying and removing empty bounding boxes. Specifically, the script eliminates bounding boxes (or entities) that lack `mentionText` or `textAnchors`, thus enhancing the accuracy of the labeling data.

## Inputs

- **PROJECT_ID**: Your Google project ID or name.
- **BUCKET_NAME**: The name of the bucket where your JSON files are stored.
- **INPUT_FOLDER_PATH**: Path to the folder containing the JSON files you wish to process. Do not include the bucket name in this path.
- **OUTPUT_FOLDER_PATH**: Path to the folder where you'd like to store the processed JSON files. Again, exclude the bucket name from this path.

**Note**: Ensure that both the input and output paths reside within the same bucket.

## Output
Upon execution, the script performs the following:

1. Identifies and deletes all bounding boxes (or entities) in the JSON file that are devoid of `mentionText` or `textAnchors`.
2. Overwrites the original JSON file with the cleaned version.
3. Generates a CSV file that lists all the entities it removed.

By using this script, you can ensure a more refined and accurate dataset by eliminating unnecessary or empty entities.
