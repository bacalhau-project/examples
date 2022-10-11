# Variables
variable "access_key" {}
variable "secret_key" {}
variable "region" {
  default = "us-east-2"
}
variable "domain_name" {
  description = "Domain name"
  default     = ""
}
variable "aRecords" {
  type    = list(string)
  default = []
}
variable "cnameRecords" {
  type    = list(string)
  default = []
}
variable "ttl" {
  description = "time to live"
  default     = 300
}
variable "app_tag" {
  description = "Environment tag"
  default     = ""
}
