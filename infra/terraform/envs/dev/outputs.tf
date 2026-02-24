output "vpc_id" {
  description = "Created VPC ID."
  value       = module.network.vpc_id
}

output "api_url" {
  description = "Public URL of the API ALB."
  value       = var.enable_https ? "https://${local.effective_api_hostname}" : "http://${local.effective_api_hostname}"
}

output "ui_url" {
  description = "Public URL of the UI ALB."
  value       = var.enable_https ? "https://${local.effective_ui_hostname}" : "http://${local.effective_ui_hostname}"
}

output "openai_secret_arn" {
  description = "OpenAI secret ARN in Secrets Manager."
  value       = module.secrets.openai_secret_arn
}

output "api_auth_secret_arn" {
  description = "API shared-key secret ARN in Secrets Manager."
  value       = module.secrets.api_auth_secret_arn
}

output "db_master_secret_arn" {
  description = "RDS-managed master user secret ARN in Secrets Manager."
  value       = module.data.db_master_secret_arn
}

output "api_ecr_repository_url" {
  description = "API ECR repository URL."
  value       = module.ecr.api_repository_url
}

output "worker_ecr_repository_url" {
  description = "Worker ECR repository URL."
  value       = module.ecr.worker_repository_url
}

output "ui_ecr_repository_url" {
  description = "UI ECR repository URL."
  value       = module.ecr.ui_repository_url
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID for UI login."
  value       = aws_cognito_user_pool.ui.id
}

output "cognito_user_pool_domain" {
  description = "Cognito hosted UI domain."
  value       = aws_cognito_user_pool_domain.ui.domain
}
