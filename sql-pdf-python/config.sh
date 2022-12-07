##################################################
##
## Set these Variables
##
##################################################
# existing GCP user that will:
# create the project
# attach a billing id (needs to have permission)
# and provision resources
export USER_EMAIL=<insert gcp user email>

# project id for your NEW GCP project
export PROJECT_ID=<insert project id>


# the new project will need to be tied to a billing account
export BILLING_ACCOUNT_ID=<insert billing account>

# desired GCP region for networking and compute resources, EDIT region below based on your need
export REGION=us-central1


##################################################
#Example
##################################################
# export USER_EMAIL=myuser@mydomain.com
# export PROJECT_ID=gee-on-gcp
# export BILLING_ACCOUNT_ID=123456-123456-123456
##################################################
