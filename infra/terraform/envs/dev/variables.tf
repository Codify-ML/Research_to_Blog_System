variable "project_name" {
  description = "Project slug used in naming and tags."
  type        = string
  default     = "vc-blog-agent"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "route53_zone_name" {
  description = "Route53 hosted zone name for app records."
  type        = string
  default     = "dev.vc-projects-ds.com"
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for app records."
  type        = string
  default     = "Z03707592Y0NKCCWRSSFL"
}

variable "api_hostname" {
  description = "Public API DNS hostname."
  type        = string
  default     = "api.vc-blog-agent.dev.vc-projects-ds.com"
}

variable "ui_hostname" {
  description = "Public UI DNS hostname."
  type        = string
  default     = "ui.vc-blog-agent.dev.vc-projects-ds.com"
}

variable "aws_region" {
  description = "AWS region for deployment."
  type        = string
  default     = "us-west-2"
}

variable "aws_profile" {
  description = "AWS profile used only for local Terraform execution."
  type        = string
  default     = "personal-aws-dev"
}

variable "vpc_cidr" {
  description = "VPC CIDR range."
  type        = string
  default     = "10.40.0.0/16"
}

variable "az_count" {
  description = "Number of Availability Zones for subnets."
  type        = number
  default     = 2
}

variable "enable_nat_gateway" {
  description = "Whether to create NAT for private subnet egress."
  type        = bool
  default     = true
}

variable "enable_https" {
  description = "Enable HTTPS listeners and HTTP redirect."
  type        = bool
  default     = true
}

variable "enable_ui_auth" {
  description = "Enable Cognito authentication for UI endpoint."
  type        = bool
  default     = true
}

variable "cognito_domain_prefix" {
  description = "Cognito hosted UI domain prefix."
  type        = string
  default     = "vc-blog-agent-dev-auth"
}

variable "db_name" {
  description = "Postgres database name."
  type        = string
  default     = "research_blog"
}

variable "db_username" {
  description = "Postgres database username."
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "Postgres database password."
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB."
  type        = number
  default     = 20
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "openai_api_key" {
  description = "Optional initial OpenAI key to write to Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true
}

variable "api_auth_key" {
  description = "Optional initial API shared key to write to Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition = !(
      var.api_auth_enabled && trimspace(var.api_auth_key) == ""
    )
    error_message = "api_auth_key must be provided when api_auth_enabled is true."
  }
}

variable "waf_rate_limit" {
  description = "Per-5-minute request limit per IP for WAF rate rule."
  type        = number
  default     = 2000
}

variable "api_auth_enabled" {
  description = "Enable API shared-key auth at application layer."
  type        = bool
  default     = true
}

variable "api_image" {
  description = "Optional override image URI for API service."
  type        = string
  default     = ""
}

variable "worker_image" {
  description = "Optional override image URI for worker service."
  type        = string
  default     = ""
}

variable "ui_image" {
  description = "Optional override image URI for UI service."
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Default image tag used when api/worker/ui_image are unset."
  type        = string
  default     = "latest"
}

variable "use_mock_llm" {
  description = "Default API mode if llm_mode is not provided by caller."
  type        = bool
  default     = false
}

variable "mock_mode_strict" {
  description = "Disable OpenAI runtime if true."
  type        = bool
  default     = false
}

variable "openai_model_researcher" {
  description = "OpenAI model used by the researcher node."
  type        = string
  default     = "gpt-4.1"
}

variable "openai_model_writer" {
  description = "OpenAI model used by the writer node."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "openai_model_editor" {
  description = "OpenAI model used by the editor node."
  type        = string
  default     = "gpt-4.1-mini"
}
