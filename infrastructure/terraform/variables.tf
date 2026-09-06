variable "aws_endpoint_url" {
  description = "AWS endpoint URL"
  type        = string
}

variable "s3_bucket_name" {
  description = "S3 Bucket Name"
  type        = string
  default     = "devtube-lakehouse"
}
