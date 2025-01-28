// variables.pkr.hcl
variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "base_ami_id" {
  type    = string
  default = "ami-07d9cf938edb0739b"  // Amazon Linux 2 AMI
}

variable "ami_name" {
  type    = string
  default = "bacalhau-scale-test-ami"
}

variable "ami_description" {
  type    = string
  default = "AMI with Docker and Bacalhau preinstalled"
}

variable "orchestrator_config" {
  type    = string
  default = "orchestrator-config.yaml"
}

variable "docker_compose" {
  type    = string
  default = "docker-compose.yaml"
}