terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

variable "aws_region" {
  description = "AWS region to deploy the telemetry foundation."
  type        = string
  default     = "eu-west-1"
}

variable "project" {
  description = "Project prefix used for resource naming."
  type        = string
  default     = "spirii-telemetry"
}

variable "environment" {
  description = "Deployment environment name (e.g. dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "lambda_memory_size" {
  description = "Default memory size (MB) for Lambda functions."
  type        = number
  default     = 256
}

variable "lambda_timeout_seconds" {
  description = "Default timeout (seconds) for Lambda functions."
  type        = number
  default     = 30
}

