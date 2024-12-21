variable "app_name" {
  type        = string
  description = "application name to propagate to resources"
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "oci_regions" {
  type        = list(string)
  description = "List of Oracle Cloud regions to deploy resources"
}

variable "oci_instance_shape" {
  type        = string
  description = "Oracle Cloud compute instance shape"
  default     = "VM.Standard2.2"
}

variable "orchestrator_config_path" {
  type        = string
  description = "Path to the Bacalhau orchestrator configuration YAML file"
}

variable "username" {
  type        = string
  description = "Username for login"
}

variable "public_key" {
  type        = string
  description = "Public key file that should appear in authorized_keys"
}

variable "bacalhau_installation_id" {
  type        = string
  description = "Bacalhau installation ID for tracking compute nodes"
}

variable "logs_dir" {
  type        = string
  description = "Directory where logs will be generated"
  default     = "/var/log/app"
}

variable "logs_to_process_dir" {
  type        = string
  description = "Directory where logs will be processed"
  default     = "/var/log/logs_to_process"
}

# Oracle-specific variables
variable "tenancy_ocid" {
  description = "Oracle tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "Oracle user OCID"
  type        = string
}

variable "fingerprint" {
  description = "API key fingerprint"
  type        = string
}

variable "compartment_id" {
  description = "Oracle compartment OCID"
  type        = string
}

variable "instances_per_region" {
  type        = number
  description = "Number of compute instances to deploy per region"
  default     = 5
}

variable "buckets_per_region" {
  type        = number
  description = "Number of storage buckets to deploy per region"
  default     = 5
}

variable "central_logging_bucket" {
  type        = string
  description = "Name of the central GCP bucket for aggregated logging"
}
