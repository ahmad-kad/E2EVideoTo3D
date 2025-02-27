variable "project_id" {
  description = "The ID of the Google Cloud project"
  type        = string
}

variable "region" {
  description = "The region to deploy resources to"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The zone to deploy resources to"
  type        = string
  default     = "us-central1-a"
}

variable "domain" {
  description = "The domain name for services"
  type        = string
  default     = "example.com"
}

variable "airflow_admin_password" {
  description = "The admin password for Airflow"
  type        = string
  sensitive   = true
} 