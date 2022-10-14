# Variables
variable "access_key" {}
variable "secret_key" {}
variable "region" {}
variable "domain_name" {
  description = "Domain name"
}
variable "aRecords" {
  type    = list(string)
}
variable "cnameRecords" {
  type    = list(string)
}
variable "ttl" {
  description = "time to live"
  default     = 300
}
variable "app_tag" {
  description = "Environment tag"
}
