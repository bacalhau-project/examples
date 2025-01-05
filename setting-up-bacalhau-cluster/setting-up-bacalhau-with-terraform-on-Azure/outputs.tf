output "vm_public_ips" {
  description = "Public IP addresses of all VMs"
  value = {
    for location, instance in module.instanceModule : location => {
      for idx in range(instance.node_count) : "vm-${idx}" => {
        public_ip  = instance.public_ips[idx]
        private_ip = instance.private_ips[idx]
      }
    }
  }
}
