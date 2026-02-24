output "api_repository_url" {
  description = "API ECR repository URL."
  value       = aws_ecr_repository.api.repository_url
}

output "worker_repository_url" {
  description = "Worker ECR repository URL."
  value       = aws_ecr_repository.worker.repository_url
}

output "ui_repository_url" {
  description = "UI ECR repository URL."
  value       = aws_ecr_repository.ui.repository_url
}

output "api_repository_name" {
  description = "API ECR repository name."
  value       = aws_ecr_repository.api.name
}

output "worker_repository_name" {
  description = "Worker ECR repository name."
  value       = aws_ecr_repository.worker.name
}

output "ui_repository_name" {
  description = "UI ECR repository name."
  value       = aws_ecr_repository.ui.name
}
