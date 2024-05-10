variable "project_id" {
  description = "The project ID to deploy to."
}

variable "bootstrap_zone" {
  description = "Zone where the bootstrap node will be created"
  type        = string
}

variable "app_name" {
  type        = string
  description = "application name to propagate to resources"
}

variable "locations" {
  description = "Locations and resources to deploy"
  type        = map(map(string))
}

variable "machine_type" {
  description = "The type of instance the applications are to run on"
  type        = string
}

variable "username" {
  type        = string
  description = "Username for login"
}

variable "public_key" {
  type        = string
  description = "Public key file that should appear in authorized_keys"
}

variable "bacalhau_run_file" {
  type        = string
  description = "Bacalhau Run File location"
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "bucket_name" {
  description = "Name of the Object Storage bucket to retrieve script files from"
  type        = string
}
