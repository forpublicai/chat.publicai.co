output "acm_validation_records" {
  description = "The DNS validation records for the ACM certificate. Add these to Cloudflare to validate the certificate."
  value = [
    for dvo in aws_acm_certificate.cert.domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  ]
}

# output "db_cluster_endpoint" {
#   description = "The cluster endpoint for the RDS Aurora PostgreSQL database"
#   value       = aws_rds_cluster.this.endpoint
# }

# data "aws_secretsmanager_secret_version" "db_password" {
#   secret_id = aws_rds_cluster.this.master_user_secret[0].secret_arn
# }

# output "db_username" {
#   description = "The master username for the database"
#   value       = aws_rds_cluster.this.master_username
# }

# output "db_password" {
#   description = "The master password for the database"
#   value       = jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"]
#   sensitive   = true
# }

# output "db_port" {
#   description = "The port the database is listening on"
#   value       = aws_rds_cluster.this.port
# }

# output "db_name" {
#   description = "The default database name"
#   value       = "postgres"
# }

output "alb_dns_name" {
  description = "The DNS name of the Application Load Balancer. Point your Cloudflare CNAME record here."
  value       = aws_lb.app.dns_name
}

