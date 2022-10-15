variable "access_key" {}
variable "secret_key" {}
variable "region" {
  default = "us-east-2"
}

variable "vpc_id" {
  description = "VPC id"
  default     = ""
}
variable "app_tag" {
  description = "Environment tag"
  default     = ""
}
