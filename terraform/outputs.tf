output "wildcard_certificate_arn" {
  value       = aws_acm_certificate_validation.wildcard.certificate_arn
  description = "ARN of the wildcard ACM certificate for EKS ALB Ingresses"
}
