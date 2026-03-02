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

variable "aws_region" {
  description = "AWS region for deployment."
  type        = string
  default     = "us-west-2"
}

variable "aws_profile" {
  description = "AWS profile used for local Terraform execution."
  type        = string
  default     = "personal-aws-dev"
}

variable "route53_zone_name" {
  description = "Route53 hosted zone name for Langfuse record."
  type        = string
  default     = "dev.vc-projects-ds.com"
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for Langfuse record."
  type        = string
  default     = "Z03707592Y0NKCCWRSSFL"
}

variable "app_dns_prefix" {
  description = "Shared DNS prefix under route53_zone_name."
  type        = string
  default     = "blog-agent"
}

variable "langfuse_dns_label" {
  description = "DNS label used for Langfuse hostname."
  type        = string
  default     = "langfuse"
}

variable "langfuse_hostname" {
  description = "Optional full hostname override for Langfuse."
  type        = string
  default     = ""
}

variable "enable_https" {
  description = "Enable HTTPS for Langfuse ALB."
  type        = bool
  default     = true
}

variable "enable_langfuse_compute" {
  description = "Deploy ECS/ALB Langfuse compute resources."
  type        = bool
  default     = false
}

variable "enable_langfuse_auth" {
  description = "Enable Cognito auth in front of Langfuse ALB."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days for Langfuse services."
  type        = number
  default     = 7
}

variable "langfuse_web_image" {
  description = "Langfuse web image URI."
  type        = string
  default     = "langfuse/langfuse:3"
}

variable "langfuse_worker_image" {
  description = "Langfuse worker image URI."
  type        = string
  default     = "langfuse/langfuse-worker:3"
}

variable "langfuse_web_desired_count" {
  description = "Desired count for Langfuse web service."
  type        = number
  default     = 1
}

variable "langfuse_worker_desired_count" {
  description = "Desired count for Langfuse worker service."
  type        = number
  default     = 1
}

variable "langfuse_clickhouse_desired_count" {
  description = "Desired count for internal ClickHouse service."
  type        = number
  default     = 1
}

variable "langfuse_web_cpu" {
  description = "Fargate CPU units for Langfuse web service."
  type        = string
  default     = "512"
}

variable "langfuse_web_memory" {
  description = "Fargate memory (MiB) for Langfuse web service."
  type        = string
  default     = "1024"
}

variable "langfuse_worker_cpu" {
  description = "Fargate CPU units for Langfuse worker service."
  type        = string
  default     = "512"
}

variable "langfuse_worker_memory" {
  description = "Fargate memory (MiB) for Langfuse worker service."
  type        = string
  default     = "1024"
}

variable "langfuse_clickhouse_cpu" {
  description = "Fargate CPU units for Langfuse ClickHouse service."
  type        = string
  default     = "512"
}

variable "langfuse_clickhouse_memory" {
  description = "Fargate memory (MiB) for Langfuse ClickHouse service."
  type        = string
  default     = "1024"
}

variable "langfuse_auth_disable_signup" {
  description = "Disable Langfuse self-sign-up."
  type        = bool
  default     = true
}

variable "langfuse_telemetry_enabled" {
  description = "Enable Langfuse telemetry."
  type        = bool
  default     = false
}

variable "langfuse_init_project_name" {
  description = "Initial project name for Langfuse bootstrap."
  type        = string
  default     = "vc-blog-agent-observability"
}

variable "langfuse_init_project_id" {
  description = "Optional project id for Langfuse bootstrap init."
  type        = string
  default     = ""
}

variable "enable_langfuse_bootstrap_init" {
  description = "Enable one-time LANGFUSE_INIT_* bootstrap on web/worker."
  type        = bool
  default     = false
}

variable "langfuse_init_org_id" {
  description = "Langfuse org id required when bootstrap init is enabled."
  type        = string
  default     = ""
}

variable "langfuse_event_bucket_name" {
  description = "Optional override for Langfuse event upload bucket."
  type        = string
  default     = ""
}

variable "langfuse_media_bucket_name" {
  description = "Optional override for Langfuse media upload bucket."
  type        = string
  default     = ""
}

variable "langfuse_s3_retention_days" {
  description = "S3 lifecycle retention (days) for Langfuse uploads."
  type        = number
  default     = 7
}

variable "langfuse_s3_force_path_style" {
  description = "Force path-style S3 addressing for Langfuse."
  type        = bool
  default     = false
}

variable "langfuse_clickhouse_user" {
  description = "ClickHouse username for Langfuse."
  type        = string
  default     = "default"
}

variable "langfuse_clickhouse_password" {
  description = "ClickHouse password for Langfuse."
  type        = string
  default     = "langfuse"
  sensitive   = true
}

variable "langfuse_clickhouse_db" {
  description = "ClickHouse database for Langfuse."
  type        = string
  default     = "default"
}

variable "langfuse_clickhouse_cluster_enabled" {
  description = "Enable ClickHouse cluster mode."
  type        = bool
  default     = false
}

variable "deployment_minimum_healthy_percent" {
  description = "Minimum healthy tasks during rolling deployments."
  type        = number
  default     = 100
}

variable "deployment_maximum_percent" {
  description = "Maximum running tasks during rolling deployments."
  type        = number
  default     = 200
}

variable "enable_deployment_circuit_breaker" {
  description = "Enable ECS circuit breaker rollback."
  type        = bool
  default     = true
}

variable "enable_scheduled_scaling" {
  description = "Enable scheduled up/down scaling for observability ECS services."
  type        = bool
  default     = false
}

variable "scheduled_scale_up_recurrence" {
  description = "Cron/Rate expression for observability scheduled scale-up."
  type        = string
  default     = "cron(0 8 ? * MON-FRI *)"
}

variable "scheduled_scale_down_recurrence" {
  description = "Cron/Rate expression for observability scheduled scale-down."
  type        = string
  default     = "cron(0 20 ? * MON-FRI *)"
}

variable "scheduled_scaling_timezone" {
  description = "IANA timezone used by observability scheduled scaling."
  type        = string
  default     = "America/Los_Angeles"
}

variable "langfuse_web_offhours_count" {
  description = "Desired Langfuse web task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "langfuse_worker_offhours_count" {
  description = "Desired Langfuse worker task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "langfuse_clickhouse_offhours_count" {
  description = "Desired Langfuse ClickHouse task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "use_app_state" {
  description = "Read shared network and Cognito values from app state."
  type        = bool
  default     = true
}

variable "app_state_bucket" {
  description = "S3 bucket containing app stack Terraform state."
  type        = string
  default     = "vc-tfstate-deploy-dev"
}

variable "app_state_key" {
  description = "Object key for app stack Terraform state."
  type        = string
  default     = "projects/vc-blog-agent/terraform/state/dev.tfstate"
}

variable "app_state_region" {
  description = "AWS region where app stack Terraform state is stored."
  type        = string
  default     = "us-west-2"
}

variable "app_state_profile" {
  description = "AWS profile used to read app stack Terraform state."
  type        = string
  default     = "personal-aws-dev"
}

variable "vpc_id" {
  description = "Optional VPC ID override when use_app_state=false."
  type        = string
  default     = ""
}

variable "public_subnet_ids" {
  description = "Optional public subnets override."
  type        = list(string)
  default     = []
}

variable "private_subnet_ids" {
  description = "Optional private subnets override."
  type        = list(string)
  default     = []
}

variable "cognito_user_pool_id" {
  description = "Optional Cognito pool id override for Langfuse auth."
  type        = string
  default     = ""
}

variable "cognito_user_pool_client_id" {
  description = "Optional Cognito app client id override."
  type        = string
  default     = ""
}

variable "cognito_user_pool_domain" {
  description = "Optional Cognito hosted domain override."
  type        = string
  default     = ""
}
