# Aurora Serverless v2 PostgreSQL with the RDS Data API (ADR 0001).
#
# Scales to 0 ACU and pauses after var.seconds_until_auto_pause idle seconds; the
# /status warm-up flow covers the 20-90 s resume (docs/spikes/aurora-resume.md).
# The master password is managed by RDS in Secrets Manager. The application never uses
# it: the Lambda runs as analytics_reader, loads run as olist_owner (secrets.tf).

resource "aws_db_subnet_group" "aurora" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_rds_cluster" "main" {
  cluster_identifier          = local.name
  engine                      = "aurora-postgresql"
  engine_mode                 = "provisioned"
  engine_version              = var.aurora_engine_version
  database_name               = var.database_name
  master_username             = "olist_admin"
  manage_master_user_password = true
  enable_http_endpoint        = true # RDS Data API
  db_subnet_group_name        = aws_db_subnet_group.aurora.name
  vpc_security_group_ids      = [aws_security_group.aurora.id]
  storage_encrypted           = true
  backup_retention_period     = 1
  copy_tags_to_snapshot       = true
  deletion_protection         = false # a rebuildable demo dataset; flip to true if that changes
  skip_final_snapshot         = true
  apply_immediately           = true

  serverlessv2_scaling_configuration {
    min_capacity             = 0
    max_capacity             = var.aurora_max_acu
    seconds_until_auto_pause = var.seconds_until_auto_pause
  }
}

resource "aws_rds_cluster_instance" "writer" {
  identifier          = "${local.name}-writer"
  cluster_identifier  = aws_rds_cluster.main.id
  instance_class      = "db.serverless"
  engine              = aws_rds_cluster.main.engine
  engine_version      = aws_rds_cluster.main.engine_version
  publicly_accessible = false
}

# aws_s3.table_import_from_s3 reads the CSVs with this role (ADR 0001 bulk load).
resource "aws_iam_role" "aurora_s3_import" {
  name = "${local.name}-aurora-s3-import"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:rds:${var.aws_region}:${local.account_id}:cluster:${local.name}" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "aurora_s3_import" {
  name = "read-raw-csvs"
  role = aws_iam_role.aurora_s3_import.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.data.arn}/raw/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.data.arn
      },
    ]
  })
}

resource "aws_rds_cluster_role_association" "s3_import" {
  db_cluster_identifier = aws_rds_cluster.main.id
  feature_name          = "s3Import"
  role_arn              = aws_iam_role.aurora_s3_import.arn
}
