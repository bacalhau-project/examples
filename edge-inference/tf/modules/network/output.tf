output "vpc_id" {
  value = aws_vpc.vpc.id
}
output "public_subnets" {
  value = [aws_subnet.subnet_public.id]
}
