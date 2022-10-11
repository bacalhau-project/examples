output "domain_name_servers" {  
  value = "${aws_route53_zone.domain.name_servers}"
}