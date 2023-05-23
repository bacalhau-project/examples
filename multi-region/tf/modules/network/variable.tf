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

variable "availability_zone" {
  description = "The availability zone for the subnet"
  type        = string
}

variable "app_tag" {
  description = "Environment tag"
  type        = string
}
