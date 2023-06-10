terraform {
  required_version = ">=1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~>3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~>3.0"
    }
  }
}
provider "azurerm" {
  tenant_id       = var.tenantId
  subscription_id = var.subscriptionId
  client_id       = var.clientId
  client_secret   = var.clientSecret
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}



data "cloudinit_config" "user_data" {

  for_each = var.locations

  # Azure VMs apparently require it to be b64 encoded
  gzip          = true
  base64_encode = true

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("cloud-init/init-vm.yml", {
      app_name : var.app_tag,

      bacalhau_service : filebase64("${path.root}/node_files/bacalhau.service"),
      ipfs_service : base64encode(file("${path.module}/node_files/ipfs.service")),
      start_bacalhau : filebase64("${path.root}/node_files/start-bacalhau.sh"),
      sensor_data_generator_py : filebase64("${path.root}/node_files/sensor_data_generator.py"),

      # Need to do the below to remove spaces and newlines from public key
      ssh_key : compact(split("\n", file(var.public_key)))[0],

      tailscale_key : var.tailscale_key,
      node_name : "${var.app_tag}-${each.key}-vm",
      username : var.username,
      region : each.value.region,
      zone : each.value.region,
      project_id : "${var.app_tag}",
    })
  }
}

resource "azurerm_resource_group" "rg" {
  for_each = var.locations
  name     = "${var.app_tag}-${each.key}-rg"
  location = each.key
}

resource "azurerm_virtual_network" "vnet" {
  for_each            = var.locations
  name                = "${var.app_tag}-${each.key}-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.rg[each.key].location
  resource_group_name = azurerm_resource_group.rg[each.key].name
}

resource "azurerm_subnet" "internal" {
  for_each             = var.locations
  name                 = "${var.app_tag}-${each.key}-internal-vnet"
  resource_group_name  = azurerm_resource_group.rg[each.key].name
  virtual_network_name = azurerm_virtual_network.vnet[each.key].name
  address_prefixes     = ["10.0.2.0/24"]
}

resource "azurerm_public_ip" "public_ip_allocator" {
  for_each            = var.locations
  name                = "${var.app_tag}-${each.key}-public-ip"
  resource_group_name = azurerm_resource_group.rg[each.key].name
  location            = azurerm_resource_group.rg[each.key].location
  allocation_method   = "Dynamic"
}

data "azurerm_public_ip" "public_ip" {
  for_each            = var.locations
  name                = azurerm_public_ip.public_ip_allocator[each.key].name
  resource_group_name = azurerm_linux_virtual_machine.instance[each.key].resource_group_name
}


resource "azurerm_network_interface" "nic" {
  for_each            = var.locations
  name                = "${var.app_tag}-${each.key}-nic"
  location            = azurerm_resource_group.rg[each.key].location
  resource_group_name = azurerm_resource_group.rg[each.key].name

  ip_configuration {
    name                          = "${var.app_tag}-${each.key}-ipConfiguration"
    subnet_id                     = azurerm_subnet.internal[each.key].id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.public_ip_allocator[each.key].id
  }
}

resource "azurerm_network_security_group" "nsg" {
  for_each            = var.locations
  name                = "${var.app_tag}-${each.key}-ssh-nsg"
  location            = azurerm_resource_group.rg[each.key].location
  resource_group_name = azurerm_resource_group.rg[each.key].name

  security_rule {
    name                       = "allow_ssh_sg"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface_security_group_association" "association" {
  for_each                  = var.locations
  network_interface_id      = azurerm_network_interface.nic[each.key].id
  network_security_group_id = azurerm_network_security_group.nsg[each.key].id
}

# Create a random password
resource "random_password" "password" {
  length           = 16
  special          = true
  override_special = "_%@"
}

resource "azurerm_linux_virtual_machine" "instance" {
  for_each              = var.locations
  name                  = "${var.app_tag}-${each.key}-vm"
  location              = azurerm_resource_group.rg[each.key].location
  resource_group_name   = azurerm_resource_group.rg[each.key].name
  network_interface_ids = [azurerm_network_interface.nic[each.key].id]
  size                  = "Standard_B1s"
  computer_name         = "${var.app_tag}-${each.key}-vm"
  admin_username        = var.username

  custom_data = data.cloudinit_config.user_data[each.key].rendered

  admin_ssh_key {
    username   = var.username
    public_key = file(var.public_key)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "UbuntuServer"
    sku       = "18.04-LTS"
    version   = "latest"
  }
}

locals {
  # Get just one of the bootstrap IP from data.azurerm_public_ip.public_ip where it is in the bootstrap region
  bootstrap_ip = data.azurerm_public_ip.public_ip[var.bootstrap_region].ip_address

  # Get all the regions except the bootstrap region and put them in a set
  non_bootstrap_regions = toset([for region in keys(var.locations) : region if region != var.bootstrap_region])
}

resource "null_resource" "copy-bacalhau-bootstrap-to-local" {
  depends_on = [azurerm_linux_virtual_machine.instance]

  connection {
    host        = local.bootstrap_ip
    port        = 22
    user        = var.username
    private_key = file(var.private_key)
  }

  provisioner "remote-exec" {
    inline = [
      "echo 'SSHD is now alive.'",
      "timeout 300 bash -c 'until [[ -s /run/bacalhau.run ]]; do sleep 1; done' && echo 'Bacalhau is now alive.'",
    ]
  }

  provisioner "local-exec" {
    command = "ssh -o StrictHostKeyChecking=no ${var.username}@${local.bootstrap_ip} 'sudo cat /run/bacalhau.run' > ${var.bacalhau_run_file}"
  }
}


resource "null_resource" "copy-to-node-if-worker" {
  // Only run this on worker nodes, not the bootstrap node
  for_each = local.non_bootstrap_regions

  depends_on = [null_resource.copy-bacalhau-bootstrap-to-local]

  connection {
    host        = data.azurerm_public_ip.public_ip[each.value].ip_address
    port        = 22
    user        = var.username
    private_key = file(var.private_key)
  }

  provisioner "file" {
    destination = "/home/${var.username}/bacalhau-bootstrap"
    content     = file(var.bacalhau_run_file)
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/${var.username}/bacalhau-bootstrap /etc/bacalhau-bootstrap",
      "sudo systemctl daemon-reload",
      "sudo systemctl restart bacalhau.service",
    ]
  }
}

