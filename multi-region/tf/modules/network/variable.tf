# Variables
variable "cidr_block_range" {
  description = "The CIDR block for the VPC"
  type        = string
}

variable "subnet1_cidr_block_range" {
  description = "The CIDR block for public subnet of VPC"
  type        = string
}

variable "subnet2_cidr_block_range" {
  description = "The CIDR block for private subnet of VPC"
  type        = string
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}
variable "public_key_path" {
  description = "Public key path"
  type        = string
}
