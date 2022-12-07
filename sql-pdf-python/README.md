# SQL over Docs
The goal of this demo is to run a BigQuery SQL and extract information from documents.

## Requirements
* Ensure the GCP user is allowed to create service accounts and assign roles
* BQ [object tables](https://cloud.google.com/bigquery/docs/object-table-introduction) need to be enabled (as of 12/5/2022 they were in private preview), if you do not have access to enable object tables manually create and load the BQ tables

## Architecture

![SQL Doc](/img/SQL-on-pdf.png)

## Setting up the demo
**1)** In Cloud Shell or other environment where you have the gcloud SDK installed, execute the following commands:
```console
gcloud components update 
cd $HOME

git clone https://github.com/dojowahi/docai-on-bigquery.git
cd ~/docai-on-bigquery
chmod +x *.sh
```

**2)** **Edit config.sh** - In your editor of choice update the variables in config.sh to reflect your desired gcp project.

**3)** Next execute the command below

```console
sh setup_sa.sh
```

**4)** Next execute the command below

```console
sh deploy_cf.sh
```

If the shell script has executed successfully,have a dataset docai and and a BQ object table repos should be created under your project in BigQuery along with a function doc_extractor
<br/><br/>
**Note: Your script will fail in creation of the BQ table project is not enabled to use object tables. Then you need to manually create the table and load pointers to the PDFs in GCS**

<br/><br/>
### Congrats! You just executed BigQuery SQL over Documents
