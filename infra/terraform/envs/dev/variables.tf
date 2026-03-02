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

  validation {
    condition = (
      trimspace(var.route53_zone_name) != ""
      && can(regex("^[A-Za-z0-9.-]+\\.?$", trimspace(var.route53_zone_name)))
    )
    error_message = "route53_zone_name must be a valid DNS zone name."
  }
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for app records."
  type        = string
  default     = "Z03707592Y0NKCCWRSSFL"
}

variable "app_dns_prefix" {
  description = "Shared DNS prefix for API/UI hostnames under route53_zone_name."
  type        = string
  default     = "blog-agent"

  validation {
    condition = (
      trimspace(var.app_dns_prefix) != ""
      && can(regex("^[a-z0-9-]+$", trimspace(var.app_dns_prefix)))
    )
    error_message = "app_dns_prefix must contain only lowercase letters, digits, or hyphens."
  }
}

variable "api_dns_label" {
  description = "DNS label used for the API hostname."
  type        = string
  default     = "api"

  validation {
    condition = (
      trimspace(var.api_dns_label) != ""
      && can(regex("^[a-z0-9-]+$", trimspace(var.api_dns_label)))
    )
    error_message = "api_dns_label must contain only lowercase letters, digits, or hyphens."
  }
}

variable "ui_dns_label" {
  description = "DNS label used for the UI hostname."
  type        = string
  default     = "ui"

  validation {
    condition = (
      trimspace(var.ui_dns_label) != ""
      && can(regex("^[a-z0-9-]+$", trimspace(var.ui_dns_label)))
    )
    error_message = "ui_dns_label must contain only lowercase letters, digits, or hyphens."
  }
}

variable "api_hostname" {
  description = "Optional full API hostname override. Defaults to derived value when empty."
  type        = string
  default     = ""

  validation {
    condition = (
      trimspace(var.api_hostname) == ""
      || endswith(
        trimsuffix(lower(trimspace(var.api_hostname)), "."),
        trimsuffix(lower(trimspace(var.route53_zone_name)), "."),
      )
    )
    error_message = "api_hostname must end with route53_zone_name when set."
  }
}

variable "ui_hostname" {
  description = "Optional full UI hostname override. Defaults to derived value when empty."
  type        = string
  default     = ""

  validation {
    condition = (
      trimspace(var.ui_hostname) == ""
      || endswith(
        trimsuffix(lower(trimspace(var.ui_hostname)), "."),
        trimsuffix(lower(trimspace(var.route53_zone_name)), "."),
      )
    )
    error_message = "ui_hostname must end with route53_zone_name when set."
  }
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
  description = "Deprecated/unused. RDS now manages master password in Secrets Manager."
  type        = string
  default     = ""
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

variable "redis_parameter_group_family" {
  description = "Redis parameter group family for ElastiCache."
  type        = string
  default     = "redis7"
}

variable "redis_maxmemory_policy" {
  description = "Redis maxmemory eviction policy."
  type        = string
  default     = "noeviction"
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

variable "langfuse_public_key" {
  description = "Optional initial Langfuse public key in Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true
}

variable "langfuse_secret_key" {
  description = "Optional initial Langfuse secret key in Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true
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

variable "ecr_image_retention_count" {
  description = "Number of most recent images to retain per app ECR repository."
  type        = number
  default     = 10
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
  description = "Enable scheduled up/down scaling for app ECS services."
  type        = bool
  default     = false
}

variable "scheduled_scale_up_recurrence" {
  description = "Cron/Rate expression for app stack scheduled scale-up."
  type        = string
  default     = "cron(0 8 ? * MON-FRI *)"
}

variable "scheduled_scale_down_recurrence" {
  description = "Cron/Rate expression for app stack scheduled scale-down."
  type        = string
  default     = "cron(0 20 ? * MON-FRI *)"
}

variable "scheduled_scaling_timezone" {
  description = "IANA timezone used by app stack scheduled scaling."
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
  description = "Enable Langfuse tracing in API and worker."
  type        = bool
  default     = false
}

variable "langfuse_host" {
  description = "Langfuse host URL for app tracing."
  type        = string
  default     = ""

  validation {
    condition = (
      !var.langfuse_enabled
      || trimspace(var.langfuse_host) != ""
    )
    error_message = "langfuse_host must be provided when tracing is enabled."
  }
}

variable "langfuse_environment" {
  description = "Langfuse environment label for traces."
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
  description = "Capture /health traces in Langfuse."
  type        = bool
  default     = false
}
