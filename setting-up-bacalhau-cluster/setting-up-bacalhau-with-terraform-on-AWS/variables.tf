variable "start_node_script_path" {
  type = string
}

variable "app_tag" {
  type = string
}

variable "aws_instance_type" {
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

variable "locations" {
  type = map(object({
    zone         = string
    instance_ami = string
    node_count   = number
  }))
}
