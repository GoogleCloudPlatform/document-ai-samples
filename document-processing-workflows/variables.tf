variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "terraform_service_account" {
  type = string
}

variable "processors" {
  type = map(object({
    location                   = string
    display_name               = string
    type                       = string
    minTrainingIntervalSeconds = optional(number)
    kms_key_name               = optional(string)
  }))
}

variable "alert_notification_email" {
  type = string
}
