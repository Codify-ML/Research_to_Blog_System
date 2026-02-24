output "db_endpoint" {
  description = "Postgres endpoint address."
  value       = aws_db_instance.postgres.address
}

output "db_port" {
  description = "Postgres endpoint port."
  value       = aws_db_instance.postgres.port
}

output "db_master_secret_arn" {
  description = "RDS-managed master user secret ARN."
  value       = try(aws_db_instance.postgres.master_user_secret[0].secret_arn, "")
}

output "redis_endpoint" {
  description = "Redis endpoint address."
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "redis_port" {
  description = "Redis endpoint port."
  value       = aws_elasticache_cluster.redis.port
}
