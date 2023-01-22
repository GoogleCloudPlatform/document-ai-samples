# document-ai-warehouse-java-samples

Document AI Warehouse can be invoked from applications written in Java.  This repository provides samples that perform
some of the most common operations including:

* Creation of a schema
* List of existing schemas
* Creation of a document
* Deletion of a document
* Searching documents

Each of the samples expects to run in an environment with Google Cloud application default credentials such that 
API requests are sent with authentication.  For the majority of the samples, a some environment variables are
also used:

* `PROJECT_NUMBER` - The Google Cloud Project Number (**not** the Project ID) of the project hosting the Document AI
Warehouse.
* `LOCATION` - The location of the Document AI Warehouse.  This is an *optional* variable that defaults to `us`.
* `USERID` - The identity of the user on whose behalf we are making the request.  For example
`user:joe@example.com`.

Here are the samples described in more detail:

#### CreateSchema
Create a new schema in Document AI Warehouse.  The schema will have a display name of `Invoice` and will
contain properties definitions for:

| name     | filterable | searchable | isMetadata | isRequired | type      |
|----------|------------|------------|------------|------------|-----------|
| `payee`  | true       | true       | true       | true       | text      |
| `payer`  | true       | false      | true       | true       | text      | 
| `amount` | true       | false      | true       | false      | float     |
| `id`     | true       | false      | true       | false      | text      |
| `date`   | true       | false      | true       | false      | Date/Time |
| `notes`  | true       | false      | true       | false      | text      |

After running the sample, the identity of the schema will be output in the format:

```text
projects/[PROJECT_NUMBER]/locations/[LOCATION]/documentSchemas/[SCHEMA_ID]
```

If you now visit the Document AI Warehouse admin panel you will be able to find the new schema.

#### ListSchema
List the existing schemas.  When this sample is run, it will list all the schemas found in Document AI Warehouse.  The
results include the display name and the identity name for each schema.

#### CreateDocument
Create a new document.  This sample creates (ingests) a new document in Document AI Warehouse.  To ingest a new
document we need a few pieces of information:

* The schema that we wish to associate with the document
* The document that we wish to ingest

We pass in positional arguments for these.  The first argument is the schema name, the second is the local file for
the document.  This document will be read and passed in.  The sample sets properties named `payer` and `payee`
which are present in the schema built in the `CreateSchema` sample.  Sample PDFs are available in the `data` folder.

#### DeleteDocument
Delete a document.  This sample deletes a document from Document AI Warehouse.  The name of the document to be deleted
is expected to be passed in as the first positional argument.

#### SearchDocuments
Search documents. This sample searches the documents for a given piece of text.  A positional parameter is expected
which is the string to search for.  The resulting output is a table containing the display name and name 
of the documents that matched.

#### CreateDocumentDocAI
One of the capabilities of Document Warehouse is to associate the results of processing a document through
Document AI with the document itself.  In this sample, we pass in positional parameters for a schema, a local file
and a Doc AI parser.  The parser is invoked to process the document and the result is then associated with a
new document in Document AI Warehouse.  Prior to use you must create a Document AI Processor.