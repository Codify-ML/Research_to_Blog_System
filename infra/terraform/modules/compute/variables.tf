variable "name_prefix" {
  description = "Prefix used for compute resource names."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs used by ALBs."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs used by ECS services."
  type        = list(string)
}

variable "vpc_id" {
  description = "VPC ID for ALBs and target groups."
  type        = string
}

variable "alb_api_sg_id" {
  description = "Security group for API ALB."
  type        = string
}

variable "alb_ui_sg_id" {
  description = "Security group for UI ALB."
  type        = string
}

variable "api_sg_id" {
  description = "Security group for API ECS service."
  type        = string
}

variable "ui_sg_id" {
  description = "Security group for UI ECS service."
  type        = string
}

variable "worker_sg_id" {
  description = "Security group for worker ECS service."
  type        = string
}

variable "task_execution_role_arn" {
  description = "ECS task execution role ARN."
  type        = string
}

variable "task_role_arn" {
  description = "ECS task role ARN."
  type        = string
}

variable "db_endpoint" {
  description = "Postgres endpoint address."
  type        = string
}

variable "db_port" {
  description = "Postgres endpoint port."
  type        = number
}

variable "db_name" {
  description = "Postgres DB name."
  type        = string
}

variable "db_username" {
  description = "Postgres DB username."
  type        = string
}

variable "db_password" {
  description = "Deprecated fallback DB password used during migration."
  type        = string
  default     = ""
  sensitive   = true
}

variable "db_secret_arn" {
  description = "RDS secret ARN containing the DB password."
  type        = string
}

variable "redis_endpoint" {
  description = "Redis endpoint address."
  type        = string
}

variable "redis_port" {
  description = "Redis endpoint port."
  type        = number
}

variable "openai_secret_arn" {
  description = "Optional OpenAI key secret ARN for ECS secrets injection."
  type        = string
  default     = ""
}

variable "api_auth_secret_arn" {
  description = "Optional API auth key secret ARN for ECS secrets injection."
  type        = string
  default     = ""
}

variable "langfuse_public_key_secret_arn" {
  description = "Optional Langfuse public key secret ARN for ECS secrets injection."
  type        = string
  default     = ""
}

variable "langfuse_secret_key_secret_arn" {
  description = "Optional Langfuse secret key secret ARN for ECS secrets injection."
  type        = string
  default     = ""
}

variable "api_image" {
  description = "Container image for API service."
  type        = string
}

variable "worker_image" {
  description = "Container image for worker service."
  type        = string
}

variable "ui_image" {
  description = "Container image for UI service."
  type        = string
}

variable "api_base_url" {
  description = "Base URL used by UI to reach API."
  type        = string
}

variable "api_auth_enabled" {
  description = "Enable API shared-key auth checks."
  type        = bool
  default     = false
}

variable "ui_cognito_hosted_ui_base" {
  description = "Base URL for Cognito hosted UI auth endpoints."
  type        = string
  default     = ""
}

variable "ui_public_base_url" {
  description = "Public base URL for the UI service."
  type        = string
  default     = ""
}

variable "use_mock_llm" {
  description = "Default LLM mode when request omits llm_mode."
  type        = bool
  default     = true
}

variable "mock_mode_strict" {
  description = "Whether OpenAI mode should be blocked globally."
  type        = bool
  default     = false
}

variable "openai_model_researcher" {
  description = "OpenAI model for researcher node."
  type        = string
  default     = "gpt-4.1"
}

variable "openai_model_writer" {
  description = "OpenAI model for writer node."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "openai_model_editor" {
  description = "OpenAI model for editor node."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "rate_limit_enabled" {
  description = "Enable API rate-limiting controls."
  type        = bool
  default     = true
}

variable "rate_limit_generate_per_minute" {
  description = "Per-identity generate request limit per minute."
  type        = number
  default     = 20
}

variable "rate_limit_status_per_minute" {
  description = "Per-identity status request limit per minute."
  type        = number
  default     = 120
}

variable "abuse_window_seconds" {
  description = "Time window for blocked-input abuse tracking."
  type        = number
  default     = 600
}

variable "abuse_violation_threshold" {
  description = "Blocked-input count threshold before cooldown."
  type        = number
  default     = 5
}

variable "abuse_cooldown_seconds" {
  description = "Cooldown duration after abuse threshold is crossed."
  type        = number
  default     = 900
}

variable "rate_limit_fail_open" {
  description = "Allow requests if Redis rate-limit backend is unavailable."
  type        = bool
  default     = true
}

variable "langfuse_enabled" {
  description = "Enable Langfuse tracing in API and worker services."
  type        = bool
  default     = false
}

variable "langfuse_host" {
  description = "Langfuse host URL used by API and worker services."
  type        = string
  default     = ""
}

variable "langfuse_environment" {
  description = "Langfuse environment label used for traces."
  type        = string
  default     = "dev"
}

variable "langfuse_sample_rate" {
  description = "Langfuse trace sampling rate."
  type        = number
  default     = 1.0
}

variable "langfuse_capture_content" {
  description = "Capture trace input/output content in Langfuse."
  type        = bool
  default     = false
}

variable "langfuse_trace_health_endpoints" {
  description = "Capture /health endpoint traces in Langfuse."
  type        = bool
  default     = false
}

variable "api_task_cpu" {
  description = "Fargate CPU units for API task."
  type        = string
  default     = "512"
}

variable "api_task_memory" {
  description = "Fargate memory (MiB) for API task."
  type        = string
  default     = "1024"
}

variable "worker_task_cpu" {
  description = "Fargate CPU units for worker task."
  type        = string
  default     = "512"
}

variable "worker_task_memory" {
  description = "Fargate memory (MiB) for worker task."
  type        = string
  default     = "1024"
}

variable "ui_task_cpu" {
  description = "Fargate CPU units for UI task."
  type        = string
  default     = "512"
}

variable "ui_task_memory" {
  description = "Fargate memory (MiB) for UI task."
  type        = string
  default     = "1024"
}

variable "ui_logout_task_cpu" {
  description = "Fargate CPU units for UI logout task."
  type        = string
  default     = "256"
}

variable "ui_logout_task_memory" {
  description = "Fargate memory (MiB) for UI logout task."
  type        = string
  default     = "512"
}

variable "api_desired_count" {
  description = "Desired number of API tasks."
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Desired number of worker tasks."
  type        = number
  default     = 1
}

variable "ui_desired_count" {
  description = "Desired number of UI tasks."
  type        = number
  default     = 1
}

variable "ui_logout_desired_count" {
  description = "Desired number of UI logout tasks."
  type        = number
  default     = 1
}

variable "deployment_minimum_healthy_percent" {
  description = "Minimum healthy tasks during ECS rolling deployments."
  type        = number
  default     = 100
}

variable "deployment_maximum_percent" {
  description = "Maximum running tasks during ECS rolling deployments."
  type        = number
  default     = 200
}

variable "enable_deployment_circuit_breaker" {
  description = "Enable ECS deployment circuit breaker with rollback."
  type        = bool
  default     = true
}

variable "enable_scheduled_scaling" {
  description = "Enable scheduled up/down scaling for ECS services."
  type        = bool
  default     = false
}

variable "scheduled_scale_up_recurrence" {
  description = "Cron/Rate expression for scheduled scale-up."
  type        = string
  default     = "cron(0 8 ? * MON-FRI *)"
}

variable "scheduled_scale_down_recurrence" {
  description = "Cron/Rate expression for scheduled scale-down."
  type        = string
  default     = "cron(0 20 ? * MON-FRI *)"
}

variable "scheduled_scaling_timezone" {
  description = "IANA timezone used by scheduled scaling actions."
  type        = string
  default     = "America/Los_Angeles"
}

variable "api_offhours_count" {
  description = "Desired API task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "worker_offhours_count" {
  description = "Desired worker task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "ui_offhours_count" {
  description = "Desired UI task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "ui_logout_offhours_count" {
  description = "Desired UI logout task count during scheduled off-hours."
  type        = number
  default     = 0
}

variable "enable_https" {
  description = "Enable HTTPS listeners and HTTP-to-HTTPS redirects."
  type        = bool
  default     = false
}

variable "certificate_arn" {
  description = "ACM certificate ARN used by ALB HTTPS listeners."
  type        = string
  default     = ""
}

variable "enable_ui_auth" {
  description = "Enable Cognito authentication on the UI listener."
  type        = bool
  default     = false
}

variable "ui_cognito_user_pool_arn" {
  description = "Cognito user pool ARN for ALB UI authentication."
  type        = string
  default     = ""
}

variable "ui_cognito_user_pool_client_id" {
  description = "Cognito app client ID for ALB UI authentication."
  type        = string
  default     = ""
}

variable "ui_cognito_user_pool_domain" {
  description = "Cognito hosted domain for ALB UI authentication."
  type        = string
  default     = ""
}
