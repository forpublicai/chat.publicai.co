output "name_servers" {
  description = "Set these 4 name servers at your domain registrar."
  value       = aws_route53_zone.this.name_servers
}
