resource "oci_core_network_security_group" "nsg" {
  compartment_id = var.compartment_id
  vcn_id         = var.vcn_id
  display_name   = "${var.app_tag}-nsg"

  freeform_tags = {
    "App" = var.app_tag
  }
}

resource "oci_core_network_security_group_security_rule" "ssh_rule" {
  network_security_group_id = oci_core_network_security_group.nsg.id
  direction                 = "INGRESS"
  protocol                 = "6" # TCP
  source                   = "0.0.0.0/0"
  source_type              = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}

resource "oci_core_network_security_group_security_rule" "bacalhau_rule" {
  network_security_group_id = oci_core_network_security_group.nsg.id
  direction                 = "INGRESS"
  protocol                 = "6" # TCP
  source                   = "0.0.0.0/0"
  source_type              = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 1234
      max = 1234
    }
  }
}

resource "oci_core_network_security_group_security_rule" "ipfs_rule" {
  network_security_group_id = oci_core_network_security_group.nsg.id
  direction                 = "INGRESS"
  protocol                 = "6" # TCP
  source                   = "0.0.0.0/0"
  source_type              = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 1235
      max = 1235
    }
  }
}
