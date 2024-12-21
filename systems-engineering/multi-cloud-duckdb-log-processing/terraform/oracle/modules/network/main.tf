resource "oci_core_vcn" "vcn" {
  compartment_id = var.compartment_id
  cidr_block     = "10.0.0.0/16"
  display_name   = "${var.app_tag}-vcn"

  freeform_tags = {
    "App" = var.app_tag
  }
}

resource "oci_core_subnet" "subnet" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.vcn.id
  cidr_block     = "10.0.1.0/24"
  display_name   = "${var.app_tag}-subnet"

  freeform_tags = {
    "App" = var.app_tag
  }
}
