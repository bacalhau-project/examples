# Variables

variable "access_key" { type = string }
variable "secret_key" { type = string }
variable "app_tag" {
  description = "Environment tag"
  type        = string
}
variable "public_key_path" {
  description = "EC2 Key pair name"
  type        = string
}
variable "locations" {
  description = "region, zone, and ami"
  type        = list(map(string))
}
variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}
variable "index" {
  description = "index of the location"
  type        = number
}
