#!/bin/bash

##################################################
##
## Set these Variables
##
##################################################
# existing GCP user that will:
# create the project
# attach a billing id (needs to have permission)
# and provision resources
export USER_EMAIL=admin@ankurwahi.altostrat.com

# project id for your NEW GCP project
export PROJECT_ID="wahi-doc-98080"


# the new project will need to be tied to a billing account, uncomment the line below for Argolis users and update value
export BILLING_ACCOUNT_ID="01F775-A9924A-26373C"

# desired GCP region for networking and compute resources, EDIT region below based on your need
export REGION=us-central1
##################################################
#Example
##################################################
# export USER_EMAIL=myuser@mydomain.com
# export PROJECT_ID=gee-on-gcp
# export BILLING_ACCOUNT_ID=123456-123456-123456
##################################################
export doc_sa=460565951168-compute@developer.gserviceaccount.com
export doc_sa=186291291334-compute@developer.gserviceaccount.com
