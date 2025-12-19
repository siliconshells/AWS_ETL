terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

# S3 Bucket
resource "aws_s3_bucket" "regulations_data" {
  bucket = "medlaunch-regulations-data"
}

resource "aws_s3_bucket_versioning" "regulations_data" {
  bucket = aws_s3_bucket.regulations_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "medlaunch-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "lambda-s3-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.regulations_data.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:*::foundation-model/anthropic.claude-v2"
      }
    ]
  })
}

# Lambda Layer
resource "aws_lambda_layer_version" "dependencies" {
  filename   = "layer.zip"
  layer_name = "medlaunch-dependencies"

  compatible_runtimes = ["python3.9"]
}

# Lambda Function
resource "aws_lambda_function" "medlaunch_processor" {
  filename         = "lambda_deployment.zip"
  function_name    = "medlaunch-regulations-processor"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_handler.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300
  layers          = [aws_lambda_layer_version.dependencies.arn]

  depends_on = [aws_iam_role_policy.lambda_s3_policy]
}

output "lambda_function_name" {
  value = aws_lambda_function.medlaunch_processor.function_name
}

output "s3_bucket_name" {
  value = aws_s3_bucket.regulations_data.bucket
}