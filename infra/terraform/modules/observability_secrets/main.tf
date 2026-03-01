resource "aws_secretsmanager_secret" "this" {
  for_each = var.secret_names

  name                    = "${var.name_prefix}/${each.key}"
  recovery_window_in_days = 0
}
