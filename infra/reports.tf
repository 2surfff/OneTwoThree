resource "random_id" "reports_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "reports" {
  bucket        = "${var.project_name}-${var.env}-reports-${random_id.reports_suffix.hex}"
  force_destroy = var.env == "dev"
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {
    status = "Enabled"
  }
}