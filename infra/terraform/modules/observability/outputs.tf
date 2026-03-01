output "alb_arn" {
  description = "Langfuse ALB ARN."
  value       = aws_lb.this.arn
}

output "alb_dns_name" {
  description = "Langfuse ALB DNS name."
  value       = aws_lb.this.dns_name
}

output "alb_zone_id" {
  description = "Langfuse ALB zone ID."
  value       = aws_lb.this.zone_id
}

output "ecs_cluster_name" {
  description = "Langfuse ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "web_service_name" {
  description = "Langfuse web ECS service name."
  value       = aws_ecs_service.web.name
}

output "worker_service_name" {
  description = "Langfuse worker ECS service name."
  value       = aws_ecs_service.worker.name
}

output "service_security_group_id" {
  description = "Security group ID used by Langfuse web and worker tasks."
  value       = aws_security_group.service.id
}
