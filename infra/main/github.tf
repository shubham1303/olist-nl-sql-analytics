# Continuous deployment from GitHub Actions with no stored AWS keys (Phase 8).
#
# The deploy workflow (.github/workflows/deploy.yml) gets short-lived credentials through
# GitHub's OIDC provider. Only runs on this repository's main branch may assume the role,
# so pull requests, forks included, can't. The role can deploy code and nothing else:
# upload the built UI, invalidate the CloudFront cache, update the Lambda code.
# Infrastructure changes stay a reviewed, manual `terraform apply`.

# GitHub's OIDC subject for this repository. It uses the immutable format, owner and
# repository names plus their numeric IDs, so a renamed or re-created repository with the
# same name can't deploy. Read it with:
#   gh api repos/OWNER/REPO/actions/oidc/customization/sub   (sub_claim_prefix)
variable "github_oidc_sub_prefix" {
  description = "sub_claim_prefix of the repository allowed to deploy (immutable subject format)."
  type        = string
  default     = "repo:shubham1303@23360808/olist-nl-sql-analytics@1384310424"
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

resource "aws_iam_role" "github_deploy" {
  name                 = "${local.name}-github-deploy"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "${var.github_oidc_sub_prefix}:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "deploy-code-only"
  role = aws_iam_role.github_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListSite"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.site.arn
      },
      {
        Sid      = "WriteSite"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.site.arn}/*"
      },
      {
        Sid      = "InvalidateCache"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
        Resource = aws_cloudfront_distribution.site.arn
      },
      {
        Sid      = "UpdateFunctionCode"
        Effect   = "Allow"
        Action   = ["lambda:UpdateFunctionCode", "lambda:GetFunction", "lambda:GetFunctionConfiguration"]
        Resource = aws_lambda_function.api.arn
      },
    ]
  })
}
