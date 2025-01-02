output "instance_ips" {
  description = "IP addresses of all instances by region"
  value = {
    for k, instance in google_compute_instance.gcp_instance : k => {
      name        = instance.name
      internal_ip = instance.network_interface[0].network_ip
      external_ip = instance.network_interface[0].access_config[0].nat_ip
      zone        = instance.zone
    }
  }
}
