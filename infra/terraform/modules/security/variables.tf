variable "name_prefix" {
  description = "Prefix used for security resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where security groups will be created."
  type        = string
}

variable "openai_secret_arn" {
  description = "Optional OpenAI secret ARN for task role access policy."
  type        = string
  default     = ""
}

variable "api_auth_secret_arn" {
  description = "Optional API auth secret ARN for task role access policy."
  type        = string
  default     = ""
}
