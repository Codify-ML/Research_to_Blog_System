output "openai_secret_arn" {
  description = "ARN of the OpenAI API key secret."
  value       = aws_secretsmanager_secret.openai_api_key.arn
}

output "api_auth_secret_arn" {
  description = "ARN of the API shared-key secret."
  value       = aws_secretsmanager_secret.api_auth_key.arn
}
