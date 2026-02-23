resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.name_prefix}/openai_api_key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  count = trimspace(var.openai_api_key) != "" ? 1 : 0

  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}
