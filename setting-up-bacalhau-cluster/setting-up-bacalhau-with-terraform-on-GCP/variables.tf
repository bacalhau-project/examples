variable "org_id" {
  description = "The GCP organization ID"
  type        = string
}

variable "gcp_billing_account_id" {
  description = "The GCP billing account ID"
  type        = string
}

variable "gcp_user_email" {
  description = "The email of the GCP user to grant owner permissions"
  type        = string
}

variable "base_project_name" {
  description = "Base name for the project (will be appended with timestamp)"
  type        = string
}

variable "locations" {
  type = map(object({
    machine_type = string
    zone         = string
  }))
}

variable "username" {
  description = "Username for SSH access"
  type        = string
}

variable "public_key" {
  description = "Path to public SSH key"
  type        = string
}

variable "bacalhau_data_dir" {
  description = "Directory for Bacalhau data"
  type        = string
}

variable "bacalhau_node_dir" {
  description = "Directory for Bacalhau node"
  type        = string
}

variable "bootstrap_project_id" {
  description = "Existing project ID to use for creating new projects"
  type        = string
}

variable "app_tag" {
  description = "Custom tag for the application (e.g., compute-cluster-prod)"
  type        = string
}
