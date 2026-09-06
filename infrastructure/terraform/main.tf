resource "aws_s3_bucket" "devtube_bucket" {
  bucket        = var.s3_bucket_name
  force_destroy = true

  tags = {
    Name        = "Devtube Lakehouse"
    Environment = "Dev"
  }
}

resource "aws_s3_bucket_versioning" "devtube_bucket_versioning" {
  bucket = aws_s3_bucket.devtube_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}
