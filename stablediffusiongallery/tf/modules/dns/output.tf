output "domain_name_servers" {
  value = aws_route53_zone.domain.name_servers
}

output "domain_name" {
  value = aws_route53_zone.domain.name
}

output "a_record_item" {
  value = aws_route53_record.a_record_item
}

output "cname_record_item" {
  value = aws_route53_record.cname_record_item
}
