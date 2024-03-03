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
variable "bacalhau_run_file" {
  type        = string
  description = "Bacalhau Run File location"
}

variable "public_key" {
  type        = string
  description = "Public key file that should appear in authorized_keys"
}

variable "private_key" {
  type        = string
  description = "Private key file used to connect to the instance"
}
