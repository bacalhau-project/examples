locals {
  create_node_info = base64encode(file("${path.module}/node_files/create_node_info.sh"))
}

# Use in your template
data "template_file" "cloud_init" {
  template = file("${path.module}/cloud-init/init-vm.yml")
  vars = {
    # ... other variables ...
    create_node_info = local.create_node_info
  }
} 
