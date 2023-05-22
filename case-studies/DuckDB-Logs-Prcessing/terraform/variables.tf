variable "project_id" {
  description = "The project ID to deploy to."
}

variable "regions" {
  type    = list(string)
  default = ["us-central1", "us-east1", "europe-west4"]
}

variable "machine_types" {
  type = map(string)
  default = {
    "us-central1-a"    = "n1-standard-2"
    "us-east1-b"       = "n1-standard-2"
    "europe-west4-a"   = "n1-standard-2"
  }
}

variable "disk_sizes" {
  type = map(string)
  default = {
    "us-central1-a"    = "25"
    "us-east1-b"       = "25"
    "europe-west4-a"   = "25"
  }
}