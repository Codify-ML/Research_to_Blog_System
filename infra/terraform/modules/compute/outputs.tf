output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "api_alb_dns_name" {
  description = "Public DNS name of API ALB."
  value       = aws_lb.api.dns_name
}

output "api_alb_zone_id" {
  description = "Canonical hosted zone ID of API ALB."
  value       = aws_lb.api.zone_id
}

output "api_alb_arn" {
  description = "ARN of API ALB."
  value       = aws_lb.api.arn
}

output "ui_alb_dns_name" {
  description = "Public DNS name of UI ALB."
  value       = aws_lb.ui.dns_name
}

output "ui_alb_zone_id" {
  description = "Canonical hosted zone ID of UI ALB."
  value       = aws_lb.ui.zone_id
}

output "ui_alb_arn" {
  description = "ARN of UI ALB."
  value       = aws_lb.ui.arn
}
