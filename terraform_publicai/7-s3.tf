data "aws_s3_bucket" "bucket" {
  bucket = "publicai-bucket"
}

resource "aws_iam_policy" "s3_access" {
  name        = "${local.env}-s3-access-policy"
  description = "Permissions for pods to access S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          data.aws_s3_bucket.bucket.arn,
          "${data.aws_s3_bucket.bucket.arn}/*"
        ]
      }
    ]
  })
}
