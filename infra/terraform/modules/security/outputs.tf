output "alb_api_sg_id" {
  description = "Security group ID for API ALB."
  value       = aws_security_group.alb_api.id
}

output "alb_ui_sg_id" {
  description = "Security group ID for UI ALB."
  value       = aws_security_group.alb_ui.id
}

output "api_sg_id" {
  description = "Security group ID for API service."
  value       = aws_security_group.api.id
}

output "ui_sg_id" {
  description = "Security group ID for UI service."
  value       = aws_security_group.ui.id
}

output "worker_sg_id" {
  description = "Security group ID for worker service."
  value       = aws_security_group.worker.id
}

output "db_sg_id" {
  description = "Security group ID for Postgres."
  value       = aws_security_group.db.id
}

output "redis_sg_id" {
  description = "Security group ID for Redis."
  value       = aws_security_group.redis.id
}

output "task_execution_role_arn" {
  description = "ECS task execution role ARN."
  value       = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  description = "ECS task role ARN."
  value       = aws_iam_role.task.arn
}

output "task_execution_role_name" {
  description = "ECS task execution role name."
  value       = aws_iam_role.task_execution.name
}

output "task_role_name" {
  description = "ECS task role name."
  value       = aws_iam_role.task.name
}
