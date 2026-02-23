output "openai_secret_arn" {
  description = "ARN of the OpenAI API key secret."
  value       = aws_secretsmanager_secret.openai_api_key.arn
}
