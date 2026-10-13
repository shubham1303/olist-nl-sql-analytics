terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state in the bucket created by infra/bootstrap (ADR 0009). The bucket name
  # contains the account ID, so it's passed at init time, not committed:
  #   terraform init -backend-config="bucket=$(terraform -chdir=../bootstrap output -raw state_bucket)"
  # Locking uses S3 native lock files.
  backend "s3" {
    key          = "main/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
