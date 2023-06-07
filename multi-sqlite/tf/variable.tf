# Variables

variable "clientId" {
  description = "Azure Client ID"
  type        = string
}

variable "clientSecret" {
  description = "Azure Client Secret"
  type        = string
}

variable "subscriptionId" {
  description = "Azure Subscription ID"
  type        = string
}

variable "tenantId" {
  description = "Azure Tenant ID"
  type        = string
}


variable "app_tag" {
  description = "Environment tag"
  type        = string
}
variable "locations" {
  description = "region"
  type        = map(map(string))
}
variable "instance_type" {
  description = "EC2 instance type"
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

variable "username" {
  description = "Username to use for SSH connection"
  type        = string
}
