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

variable "app_tag" {
  description = "Environment tag"
  type        = string
}

variable "region" {
  description = "Oracle region"
  type        = string
}

variable "locations" {
  description = "Locations and resources to deploy"
  type        = map(map(string))
}

variable "instance_shape" {
  description = "Oracle compute instance shape"
  type        = string
}

variable "bootstrap_region" {
  description = "Region where the bootstrap node will be created"
  type        = string
}

variable "bacalhau_run_file" {
  type        = string
  description = "Bacalhau Run File location"
}

variable "ssh_user" {
  type        = string
  description = "SSH username for instances"
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
