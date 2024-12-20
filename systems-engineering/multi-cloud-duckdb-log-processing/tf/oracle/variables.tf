variable "project_id" {
  description = "The project ID to deploy to."
}

variable "app_name" {
  type        = string
  description = "application name to propagate to resources"
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "locations" {
  description = "Locations and resources to deploy"
  type        = map(map(string))
}

variable "machine_type" {
  type        = string
  description = "Machine type to use for the instances"
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

variable "private_key" {
  type        = string
  description = "Private key file used to connect to the instance"
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

variable "docker_compose_path" {
  type        = string
  description = "Path to the Docker Compose file"
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

variable "private_key_path" {
  description = "Path to API private key"
  type        = string
}

variable "compartment_id" {
  description = "Oracle compartment OCID"
  type        = string
}

variable "tailscale_key" {
  description = "Tailscale key"
  type        = string
}
