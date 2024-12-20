variable "compartment_id" {
  type        = string
  description = "Oracle compartment OCID"
}

variable "region" {
  type        = string
  description = "Oracle region"
}

variable "app_tag" {
  type        = string
  description = "Application tag"
}

variable "instance_shape" {
  type        = string
  description = "Instance shape"
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID"
}

variable "nsg_ids" {
  type        = list(string)
  description = "Network security group IDs"
}

variable "username" {
  type        = string
  description = "Username for login"
}

variable "public_key" {
  type        = string
  description = "Public key file path"
}

variable "orchestrator_config_path" {
  type        = string
  description = "Path to the Bacalhau orchestrator configuration YAML file"
}
