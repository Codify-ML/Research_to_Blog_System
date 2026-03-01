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

variable "langfuse_public_key_secret_arn" {
  description = "Optional Langfuse public key secret ARN for task role access policy."
  type        = string
  default     = ""
}

variable "langfuse_secret_key_secret_arn" {
  description = "Optional Langfuse secret key secret ARN for task role access policy."
  type        = string
  default     = ""
}

variable "additional_db_ingress_sg_ids" {
  description = "Additional security group IDs allowed to connect to Postgres."
  type        = list(string)
  default     = []
}

variable "additional_redis_ingress_sg_ids" {
  description = "Additional security group IDs allowed to connect to Redis."
  type        = list(string)
  default     = []
}
