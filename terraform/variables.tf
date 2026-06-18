variable "google_client_id" {
  type        = string
  description = "Google OAuth Client ID for Cognito Identity Provider"
}

variable "google_client_secret" {
  type        = string
  description = "Google OAuth Client Secret for Cognito Identity Provider"
  sensitive   = true
}
