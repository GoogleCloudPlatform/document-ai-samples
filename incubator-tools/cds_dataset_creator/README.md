# Creating CDS Dataset from Various GCP Folders

## Objective

This document highlights the solution for generating shoeboxes (PDF files with multiple documents inside - a composite document - in random order) automatically from a collection of folders (each with a document type) present in a GCP Storage bucket. Each folder should contain a dataset of a specific document type like W2, 1030, Paystub Forms etc. 

The python script provided in this document helps to create the set of “shoebox (composite PDF) documents  based on the number of documents that should be pulled from each folder for each shoebox. The flexibility is given to you to configure

* The number of shoebox files to be created, and 
* The weight distribution for each type of document per shoebox. 

The order of the documents in the PDF are random and not repeated for every shoebox file that is created. 

Lastly, two final steps: 
1. The DocumentAI OCR processor type process documents, API is triggered for the files to generate Google Document JSONs, and 
2. The JSON has CDS-compliant entities injected that reflect how the PDF document was composed: which document type for what pages. 

## Prerequisites

* Vertex AI Notebook.
* Document AI
* Storage Bucket for storing input PDF files and output JSON files.
* Permission For Google Storage and Vertex AI Notebook.