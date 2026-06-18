resource "aws_budgets_budget" "daily_overspend" {
  account_id        = data.aws_caller_identity.current.account_id
  budget_type       = "COST"
  limit_amount      = "60.0"
  limit_unit        = "USD"
  name              = "Daily overspend (TF Managed)"
  tags              = {}
  tags_all          = {}
  time_period_end   = "2087-06-15_00:00"
  time_period_start = "2026-06-04_00:00"
  time_unit         = "DAILY"
  notification {
    comparison_operator        = "GREATER_THAN"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [local.alert_email]
    subscriber_sns_topic_arns  = []
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
  }
}
