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
variable "bootstrap_zone" {
  description = "Zone where the bootstrap node will be created"
  type        = string
}
variable "bacalhau_run_file" {
  type        = string
  description = "Bacalhau Run File location"
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

variable "tailscale_key" {
  description = "Tailscale key"
  type        = string
}

variable "motherduck_key" {
  description = "Motherduck key"
  type        = string
}
