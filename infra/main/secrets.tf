# Login secrets for the two application roles (ADR 0002), in the shape the RDS Data API
# expects. The roles themselves are created inside the database by
# `python -m olist_nlsql.dbsetup aws-build`, which reads these passwords.
#
# The passwords are generated here, so they also sit in Terraform state. The state is
# in a private, encrypted, versioned bucket (infra/bootstrap). Rotating means
# `terraform apply -replace=random_password.reader` and then re-running aws-build.

resource "random_password" "owner" {
  length  = 40
  special = false # Data API and SQL literals: no quoting surprises
}

resource "random_password" "reader" {
  length  = 40
  special = false
}

resource "aws_secretsmanager_secret" "owner" {
  name                    = "${local.name}/db/olist_owner"
  description             = "olist_owner: builds the raw and analytics schemas (aws-build only)"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "owner" {
  secret_id = aws_secretsmanager_secret.owner.id
  secret_string = jsonencode({
    username            = "olist_owner"
    password            = random_password.owner.result
    engine              = "postgres"
    dbClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  })
}

resource "aws_secretsmanager_secret" "reader" {
  name                    = "${local.name}/db/analytics_reader"
  description             = "analytics_reader: the only role the Lambda uses (read-only, analytics schema)"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "reader" {
  secret_id = aws_secretsmanager_secret.reader.id
  secret_string = jsonencode({
    username            = "analytics_reader"
    password            = random_password.reader.result
    engine              = "postgres"
    dbClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  })
}
