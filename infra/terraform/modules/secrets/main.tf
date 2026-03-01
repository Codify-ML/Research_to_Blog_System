resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.name_prefix}/openai_api_key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  count = trimspace(var.openai_api_key) != "" ? 1 : 0

  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}

resource "aws_secretsmanager_secret" "api_auth_key" {
  name                    = "${var.name_prefix}/api_auth_key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "api_auth_key" {
  count = trimspace(var.api_auth_key) != "" ? 1 : 0

  secret_id     = aws_secretsmanager_secret.api_auth_key.id
  secret_string = var.api_auth_key
}

resource "aws_secretsmanager_secret" "langfuse_public_key" {
  name                    = "${var.name_prefix}/langfuse_public_key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "langfuse_public_key" {
  count = trimspace(var.langfuse_public_key) != "" ? 1 : 0

  secret_id     = aws_secretsmanager_secret.langfuse_public_key.id
  secret_string = var.langfuse_public_key
}

resource "aws_secretsmanager_secret" "langfuse_secret_key" {
  name                    = "${var.name_prefix}/langfuse_secret_key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "langfuse_secret_key" {
  count = trimspace(var.langfuse_secret_key) != "" ? 1 : 0

  secret_id     = aws_secretsmanager_secret.langfuse_secret_key.id
  secret_string = var.langfuse_secret_key
}
