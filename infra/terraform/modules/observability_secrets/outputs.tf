output "secret_arns" {
  description = "Map of Langfuse secret ARNs keyed by secret name."
  value = {
    for key, secret in aws_secretsmanager_secret.this : key => secret.arn
  }
}

output "secret_names" {
  description = "Map of AWS secret names keyed by secret key."
  value = {
    for key, secret in aws_secretsmanager_secret.this : key => secret.name
  }
}
