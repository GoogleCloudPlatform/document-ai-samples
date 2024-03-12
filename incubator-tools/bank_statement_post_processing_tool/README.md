# Purpose and Description

This tool is designed to take bank statements from Google Cloud Storage (GCS) and parse them via a DocAI bank statement processor and post process the response from the parser (post processing as per gatless requirement in project specs) then provide the output in json format.

Below are the steps the tool will follow :

* 1.Bank statements are parsed through the bank statement processor.
* 2.Post-processing the response from the bank statement processor and saving the result in json format in the bucket.
* 3.This scipt includes the option to parse checks for the top three banks, where it is required to train a CDE model.
* 4.Top Three Banks: WellsFargo, Bank Of America, Chase

<img src="./images/image2.png" width=800 height=400 alt="images2"></img>

## Input Details

* **Project name**: Enter the google cloud project name.
* **Project_Id**: Enter the google cloud project id.
* **Processor_Id**: Enter the bank statement processor id.
* **gcs_input_dir**: Enter the path of files which have to be parsed.
* **gcs_output_dir**: Enter the path of files where you want to save the output jsons after processing the files to bank statement parser.
* **gcs_new_output_json_path**: Enter the path where the post processed json files have to be saved.
* **checksFlag** : True. Checks Flag, if True, It will use CDE Model to parse the checks table

Update the checksFlag as True if you need checks to be parsed thru cde trained parser else it can be marked as False

Fill the below details only  the checksFlag is TRUE else not needed

* **Processor_id_checks**: Enter the CDE trained processor id.
* **Processor_version_checks**: Enter the CDE trained processor version.

## Output Details

The Trained processor will detect the check entities but with the characteristic of detecting the whole row as a parent item(check_item) , if there are multiple tables (horizontally stacked).

<img src="./images/image3.png" width=800 height=400 alt="image3"></img>

The above issue is taken care of in the post processing code and below is the output after post processing code.

<img src="./images/image8.png" width=800 height=400 alt="image8"></img>
