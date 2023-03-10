project_id                = "my-project"
terraform_service_account = "terraform@my-project.iam.gserviceaccount.com"
region                    = "europe-west3"
processors = {
  "default" = {
    display_name = "default"
    location     = "eu"
    type         = "INVOICE_PROCESSOR"
  }
}

alert_notification_email = "admin@example.com"