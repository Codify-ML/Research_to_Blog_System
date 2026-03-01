output "langfuse_url" {
  description = "Public Langfuse URL."
  value       = "https://${local.effective_hostname}"
}

output "langfuse_secret_arns" {
  description = "Langfuse Secrets Manager ARNs."
  value       = module.langfuse_secrets.secret_arns
  sensitive   = true
}

output "langfuse_secret_names" {
  description = "Langfuse secret names in Secrets Manager."
  value       = module.langfuse_secrets.secret_names
}

output "langfuse_alb_dns_name" {
  description = "ALB DNS name for Langfuse (if compute enabled)."
  value       = try(module.langfuse_compute[0].alb_dns_name, null)
}

output "langfuse_cluster_name" {
  description = "ECS cluster name for Langfuse (if compute enabled)."
  value       = try(module.langfuse_compute[0].ecs_cluster_name, null)
}

output "langfuse_event_bucket_name" {
  description = "S3 bucket used for Langfuse event uploads."
  value       = aws_s3_bucket.langfuse_events.bucket
}

output "langfuse_media_bucket_name" {
  description = "S3 bucket used for Langfuse media uploads."
  value       = aws_s3_bucket.langfuse_media.bucket
}
