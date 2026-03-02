variable "name_prefix" {
  description = "Prefix used for Langfuse compute resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for ALB and ECS services."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for internet-facing ALB."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks."
  type        = list(string)
}

variable "langfuse_public_url" {
  description = "Public URL that users access for Langfuse."
  type        = string
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

variable "enable_https" {
  description = "Enable HTTPS listener and HTTP to HTTPS redirect."
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS listener."
  type        = string
  default     = ""
}

variable "enable_auth" {
  description = "Enable ALB authenticate-cognito before forwarding."
  type        = bool
  default     = true
}

variable "cognito_user_pool_arn" {
  description = "Cognito user pool ARN used for ALB authentication."
  type        = string
  default     = ""
}

variable "cognito_user_pool_client_id" {
  description = "Cognito user pool client id for ALB authentication."
  type        = string
  default     = ""
}

variable "cognito_user_pool_domain" {
  description = "Cognito hosted UI domain prefix."
  type        = string
  default     = ""
}

variable "web_desired_count" {
  description = "Desired task count for Langfuse web service."
  type        = number
  default     = 2
}

variable "worker_desired_count" {
  description = "Desired task count for Langfuse worker service."
  type        = number
  default     = 1
}

variable "web_cpu" {
  description = "Fargate CPU units for Langfuse web task."
  type        = string
  default     = "1024"
}

variable "web_memory" {
  description = "Fargate memory for Langfuse web task."
  type        = string
  default     = "2048"
}

variable "worker_cpu" {
  description = "Fargate CPU units for Langfuse worker task."
  type        = string
  default     = "1024"
}

variable "worker_memory" {
  description = "Fargate memory for Langfuse worker task."
  type        = string
  default     = "2048"
}

variable "clickhouse_image" {
  description = "ClickHouse image URI for Langfuse backend."
  type        = string
  default     = "clickhouse/clickhouse-server:24.8-alpine"
}

variable "clickhouse_desired_count" {
  description = "Desired task count for internal ClickHouse service."
  type        = number
  default     = 1
}

variable "clickhouse_cpu" {
  description = "Fargate CPU units for ClickHouse task."
  type        = string
  default     = "1024"
}

variable "clickhouse_memory" {
  description = "Fargate memory for ClickHouse task."
  type        = string
  default     = "2048"
}

variable "log_retention_days" {
  description = "CloudWatch retention period in days."
  type        = number
  default     = 7
}

variable "telemetry_enabled" {
  description = "Enable Langfuse telemetry."
  type        = bool
  default     = false
}

variable "auth_disable_signup" {
  description = "Disable self-service sign-up in Langfuse."
  type        = bool
  default     = true
}

variable "langfuse_init_project_name" {
  description = "Initial project name created by Langfuse bootstrap."
  type        = string
  default     = "vc-blog-agent-observability"
}

variable "langfuse_init_project_id" {
  description = "Optional project id used by LANGFUSE_INIT_* bootstrap flow."
  type        = string
  default     = ""
}

variable "enable_bootstrap_init" {
  description = "Enable one-time Langfuse bootstrap init env/secrets."
  type        = bool
  default     = false
}

variable "langfuse_init_org_id" {
  description = "Langfuse org id used by LANGFUSE_INIT_* bootstrap flow."
  type        = string
  default     = ""
}

variable "clickhouse_user" {
  description = "ClickHouse username."
  type        = string
  default     = "default"
}

variable "clickhouse_password" {
  description = "ClickHouse password."
  type        = string
  default     = "langfuse"
  sensitive   = true
}

variable "clickhouse_db" {
  description = "ClickHouse database name."
  type        = string
  default     = "default"
}

variable "clickhouse_cluster_enabled" {
  description = "Enable ClickHouse cluster mode."
  type        = bool
  default     = false
}

variable "s3_event_upload_bucket" {
  description = "Bucket name for Langfuse event uploads."
  type        = string
}

variable "s3_event_upload_region" {
  description = "Region for Langfuse event upload bucket."
  type        = string
}

variable "s3_media_upload_bucket" {
  description = "Bucket name for Langfuse media uploads."
  type        = string
}

variable "s3_media_upload_region" {
  description = "Region for Langfuse media upload bucket."
  type        = string
}

variable "s3_force_path_style" {
  description = "Force path-style S3 addressing."
  type        = bool
  default     = false
}

variable "deployment_minimum_healthy_percent" {
  description = "Minimum healthy tasks during rolling deploys."
  type        = number
  default     = 100
}

variable "deployment_maximum_percent" {
  description = "Maximum running tasks during rolling deploys."
  type        = number
  default     = 200
}

variable "enable_deployment_circuit_breaker" {
  description = "Enable rollback on failed ECS deployments."
  type        = bool
  default     = true
}

variable "enable_scheduled_scaling" {
  description = "Enable scheduled up/down scaling for Langfuse ECS services."
  type        = bool
  default     = false
}

variable "scheduled_scale_up_recurrence" {
  description = "Cron/Rate expression for Langfuse scheduled scale-up."
  type        = string
  default     = "cron(0 8 ? * MON-FRI *)"
}

variable "scheduled_scale_down_recurrence" {
  description = "Cron/Rate expression for Langfuse scheduled scale-down."
  type        = string
  default     = "cron(0 20 ? * MON-FRI *)"
}

variable "scheduled_scaling_timezone" {
  description = "IANA timezone used by Langfuse scheduled scaling."
  type        = string
  default     = "America/Los_Angeles"
}

variable "web_offhours_count" {
  description = "Desired Langfuse web task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "worker_offhours_count" {
  description = "Desired Langfuse worker task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "clickhouse_offhours_count" {
  description = "Desired Langfuse ClickHouse task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "database_url_secret_arn" {
  description = "Secret ARN containing DATABASE_URL."
  type        = string
}

variable "salt_secret_arn" {
  description = "Secret ARN containing SALT."
  type        = string
}

variable "encryption_key_secret_arn" {
  description = "Secret ARN containing ENCRYPTION_KEY."
  type        = string
}

variable "nextauth_secret_arn" {
  description = "Secret ARN containing NEXTAUTH_SECRET."
  type        = string
}

variable "clickhouse_url_secret_arn" {
  description = "Secret ARN containing CLICKHOUSE_URL."
  type        = string
}

variable "clickhouse_migration_url_secret_arn" {
  description = "Secret ARN containing CLICKHOUSE_MIGRATION_URL."
  type        = string
}

variable "redis_connection_string_secret_arn" {
  description = "Secret ARN containing REDIS_CONNECTION_STRING."
  type        = string
}

variable "init_user_email_secret_arn" {
  description = "Secret ARN containing LANGFUSE_INIT_USER_EMAIL."
  type        = string
  default     = ""
}

variable "init_user_name_secret_arn" {
  description = "Secret ARN containing LANGFUSE_INIT_USER_NAME."
  type        = string
  default     = ""
}

variable "init_user_password_secret_arn" {
  description = "Secret ARN containing LANGFUSE_INIT_USER_PASSWORD."
  type        = string
  default     = ""
}

variable "init_project_public_key_secret_arn" {
  description = "Secret ARN containing LANGFUSE_INIT_PROJECT_PUBLIC_KEY."
  type        = string
  default     = ""
}

variable "init_project_secret_key_secret_arn" {
  description = "Secret ARN containing LANGFUSE_INIT_PROJECT_SECRET_KEY."
  type        = string
  default     = ""
}

variable "alb_ingress_cidrs" {
  description = "Ingress CIDR blocks allowed to ALB."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
