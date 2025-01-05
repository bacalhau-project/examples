variable "app_tag" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "public_key" {
  type = string
}

variable "private_key" {
  type = string
}

variable "app_name" {
  type = string
}

variable "bacalhau_installation_id" {
  type = string
}

variable "bacalhau_data_dir" {
  type = string
}

variable "bacalhau_node_dir" {
  type = string
}

variable "username" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  type = string
}

variable "instance_ami" {
  type = string
}

variable "node_count" {
  type = number
}

variable "bacalhau_config_file_path" {
  type = string
}

variable "shared_credentials_file" {
  type = string
}
