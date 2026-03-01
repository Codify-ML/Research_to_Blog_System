locals {
  name_prefix   = "${var.project_name}-${var.environment}"
  secret_prefix = "${var.project_name}/${var.environment}/langfuse"
  canonical_app_dns_prefix = (
    startswith(trimspace(var.project_name), "vc-")
    ? trimprefix(trimspace(var.project_name), "vc-")
    : trimspace(var.project_name)
  )
  route53_zone_name_base = trimsuffix(trimspace(var.route53_zone_name), ".")
  default_hostname       = "${trimspace(var.langfuse_dns_label)}.${trimspace(var.app_dns_prefix)}.${local.route53_zone_name_base}"
  effective_hostname = (
    trimspace(var.langfuse_hostname) != ""
    ? trimsuffix(trimspace(var.langfuse_hostname), ".")
    : local.default_hostname
  )
  langfuse_scheme = var.enable_https ? "https" : "http"

  app_outputs = var.use_app_state ? data.terraform_remote_state.app[0].outputs : {}

  resolved_vpc_id = (
    trimspace(var.vpc_id) != ""
    ? trimspace(var.vpc_id)
    : try(local.app_outputs.vpc_id, "")
  )

  resolved_public_subnet_ids = (
    length(var.public_subnet_ids) > 0
    ? var.public_subnet_ids
    : try(sort(data.aws_subnets.public[0].ids), [])
  )

  resolved_private_subnet_ids = (
    length(var.private_subnet_ids) > 0
    ? var.private_subnet_ids
    : try(sort(data.aws_subnets.private[0].ids), [])
  )

  resolved_cognito_user_pool_id = (
    trimspace(var.cognito_user_pool_id) != ""
    ? trimspace(var.cognito_user_pool_id)
    : try(local.app_outputs.cognito_user_pool_id, "")
  )

  resolved_cognito_user_pool_domain = (
    trimspace(var.cognito_user_pool_domain) != ""
    ? trimspace(var.cognito_user_pool_domain)
    : try(local.app_outputs.cognito_user_pool_domain, "")
  )

  default_event_bucket_name = (
    "${var.project_name}-${var.environment}-langfuse-events-${data.aws_caller_identity.current.account_id}"
  )
  default_media_bucket_name = (
    "${var.project_name}-${var.environment}-langfuse-media-${data.aws_caller_identity.current.account_id}"
  )

  resolved_event_bucket_name = (
    trimspace(var.langfuse_event_bucket_name) != ""
    ? trimspace(var.langfuse_event_bucket_name)
    : local.default_event_bucket_name
  )

  resolved_media_bucket_name = (
    trimspace(var.langfuse_media_bucket_name) != ""
    ? trimspace(var.langfuse_media_bucket_name)
    : local.default_media_bucket_name
  )
  app_db_security_group_name    = "${var.project_name}-${var.environment}-db-sg"
  app_redis_security_group_name = "${var.project_name}-${var.environment}-redis-sg"

  secret_names = toset([
    "database_url",
    "salt",
    "encryption_key",
    "nextauth_secret",
    "clickhouse_url",
    "clickhouse_migration_url",
    "redis_connection_string",
    "init_user_email",
    "init_user_name",
    "init_user_password",
  ])

}

data "terraform_remote_state" "app" {
  count = var.use_app_state ? 1 : 0

  backend = "s3"
  config = {
    bucket  = var.app_state_bucket
    key     = var.app_state_key
    region  = var.app_state_region
    profile = var.app_state_profile
  }
}

data "aws_route53_zone" "selected" {
  zone_id = var.route53_zone_id
}

data "aws_caller_identity" "current" {}

data "aws_subnets" "public" {
  count = (
    local.resolved_vpc_id != "" && length(var.public_subnet_ids) == 0
  ) ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.resolved_vpc_id]
  }

  tags = {
    Tier = "public"
  }
}

data "aws_subnets" "private" {
  count = (
    local.resolved_vpc_id != "" && length(var.private_subnet_ids) == 0
  ) ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.resolved_vpc_id]
  }

  tags = {
    Tier = "private"
  }
}

data "aws_cognito_user_pool" "selected" {
  count = local.resolved_cognito_user_pool_id != "" ? 1 : 0

  user_pool_id = local.resolved_cognito_user_pool_id
}

data "aws_security_group" "app_db" {
  count = var.enable_langfuse_compute ? 1 : 0

  filter {
    name   = "group-name"
    values = [local.app_db_security_group_name]
  }

  filter {
    name   = "vpc-id"
    values = [local.resolved_vpc_id]
  }
}

data "aws_security_group" "app_redis" {
  count = var.enable_langfuse_compute ? 1 : 0

  filter {
    name   = "group-name"
    values = [local.app_redis_security_group_name]
  }

  filter {
    name   = "vpc-id"
    values = [local.resolved_vpc_id]
  }
}

data "aws_secretsmanager_secret" "init_project_public_key" {
  count = var.enable_langfuse_bootstrap_init ? 1 : 0

  name = "${local.secret_prefix}/init_project_public_key"
}

data "aws_secretsmanager_secret" "init_project_secret_key" {
  count = var.enable_langfuse_bootstrap_init ? 1 : 0

  name = "${local.secret_prefix}/init_project_secret_key"
}

check "route53_zone_consistency" {
  assert {
    condition = (
      trimsuffix(data.aws_route53_zone.selected.name, ".")
      == local.route53_zone_name_base
    )
    error_message = "route53_zone_id does not match route53_zone_name."
  }
}

check "app_dns_prefix_convention" {
  assert {
    condition = (
      trimspace(var.app_dns_prefix) == local.canonical_app_dns_prefix
    )
    error_message = "app_dns_prefix must follow project_name naming convention (e.g. vc-blog-agent -> blog-agent)."
  }
}

check "langfuse_network_ready" {
  assert {
    condition = (
      !var.enable_langfuse_compute
      || (
        local.resolved_vpc_id != ""
        && length(local.resolved_public_subnet_ids) > 0
        && length(local.resolved_private_subnet_ids) > 0
      )
    )
    error_message = "Missing VPC/subnet values for Langfuse compute."
  }
}

check "langfuse_auth_ready" {
  assert {
    condition = (
      !var.enable_langfuse_compute
      || !var.enable_langfuse_auth
      || (
        local.resolved_cognito_user_pool_domain != ""
        && local.resolved_cognito_user_pool_id != ""
      )
    )
    error_message = "Missing Cognito user pool/domain values for Langfuse auth."
  }
}

check "langfuse_bucket_names_distinct" {
  assert {
    condition = (
      local.resolved_event_bucket_name != local.resolved_media_bucket_name
    )
    error_message = "Langfuse event/media bucket names must be different."
  }
}

resource "aws_acm_certificate" "langfuse" {
  count = (var.enable_langfuse_compute && var.enable_https) ? 1 : 0

  domain_name       = local.effective_hostname
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = (
    var.enable_langfuse_compute && var.enable_https
    ? {
      for dvo in aws_acm_certificate.langfuse[0].domain_validation_options :
      dvo.domain_name => {
        name   = dvo.resource_record_name
        record = dvo.resource_record_value
        type   = dvo.resource_record_type
      }
    }
    : {}
  )

  zone_id         = data.aws_route53_zone.selected.zone_id
  name            = each.value.name
  type            = each.value.type
  allow_overwrite = true
  ttl             = 60
  records         = [each.value.record]
}

resource "aws_acm_certificate_validation" "langfuse" {
  count = (var.enable_langfuse_compute && var.enable_https) ? 1 : 0

  certificate_arn = aws_acm_certificate.langfuse[0].arn
  validation_record_fqdns = [
    for record in aws_route53_record.cert_validation : record.fqdn
  ]
}

resource "aws_cognito_user_pool_client" "langfuse" {
  count = (
    var.enable_langfuse_compute
    && var.enable_langfuse_auth
    && local.resolved_cognito_user_pool_id != ""
  ) ? 1 : 0

  name         = "${local.name_prefix}-langfuse-client"
  user_pool_id = local.resolved_cognito_user_pool_id

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls = [
    "${local.langfuse_scheme}://${local.effective_hostname}/oauth2/idpresponse",
  ]
  logout_urls = [
    "${local.langfuse_scheme}://${local.effective_hostname}/",
  ]
  supported_identity_providers = ["COGNITO"]

  generate_secret = true
}

module "langfuse_secrets" {
  source = "../../modules/observability_secrets"

  name_prefix  = local.secret_prefix
  secret_names = local.secret_names
}

resource "aws_s3_bucket" "langfuse_events" {
  bucket = local.resolved_event_bucket_name
}

resource "aws_s3_bucket_public_access_block" "langfuse_events" {
  bucket = aws_s3_bucket.langfuse_events.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "langfuse_events" {
  bucket = aws_s3_bucket.langfuse_events.id

  rule {
    id     = "expire-events"
    status = "Enabled"
    filter {}

    expiration {
      days = var.langfuse_s3_retention_days
    }
  }
}

resource "aws_s3_bucket" "langfuse_media" {
  bucket = local.resolved_media_bucket_name
}

resource "aws_s3_bucket_public_access_block" "langfuse_media" {
  bucket = aws_s3_bucket.langfuse_media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "langfuse_media" {
  bucket = aws_s3_bucket.langfuse_media.id

  rule {
    id     = "expire-media"
    status = "Enabled"
    filter {}

    expiration {
      days = var.langfuse_s3_retention_days
    }
  }
}

module "langfuse_compute" {
  count  = var.enable_langfuse_compute ? 1 : 0
  source = "../../modules/observability"

  name_prefix        = local.name_prefix
  vpc_id             = local.resolved_vpc_id
  public_subnet_ids  = local.resolved_public_subnet_ids
  private_subnet_ids = local.resolved_private_subnet_ids

  langfuse_public_url   = "${local.langfuse_scheme}://${local.effective_hostname}"
  langfuse_web_image    = var.langfuse_web_image
  langfuse_worker_image = var.langfuse_worker_image
  enable_https          = var.enable_https
  certificate_arn = (
    var.enable_https ? aws_acm_certificate_validation.langfuse[0].certificate_arn : ""
  )

  enable_auth           = var.enable_langfuse_auth
  cognito_user_pool_arn = try(data.aws_cognito_user_pool.selected[0].arn, "")
  cognito_user_pool_client_id = (
    var.enable_langfuse_compute && var.enable_langfuse_auth
    ? aws_cognito_user_pool_client.langfuse[0].id
    : ""
  )
  cognito_user_pool_domain = local.resolved_cognito_user_pool_domain

  web_desired_count    = var.langfuse_web_desired_count
  worker_desired_count = var.langfuse_worker_desired_count
  log_retention_days   = var.log_retention_days

  telemetry_enabled          = var.langfuse_telemetry_enabled
  auth_disable_signup        = var.langfuse_auth_disable_signup
  langfuse_init_project_name = var.langfuse_init_project_name
  langfuse_init_project_id   = var.langfuse_init_project_id
  enable_bootstrap_init      = var.enable_langfuse_bootstrap_init
  langfuse_init_org_id       = var.langfuse_init_org_id
  clickhouse_user            = var.langfuse_clickhouse_user
  clickhouse_password        = var.langfuse_clickhouse_password
  clickhouse_db              = var.langfuse_clickhouse_db
  clickhouse_cluster_enabled = var.langfuse_clickhouse_cluster_enabled
  s3_event_upload_bucket     = aws_s3_bucket.langfuse_events.bucket
  s3_event_upload_region     = var.aws_region
  s3_media_upload_bucket     = aws_s3_bucket.langfuse_media.bucket
  s3_media_upload_region     = var.aws_region
  s3_force_path_style        = var.langfuse_s3_force_path_style

  deployment_minimum_healthy_percent = (
    var.deployment_minimum_healthy_percent
  )
  deployment_maximum_percent = var.deployment_maximum_percent
  enable_deployment_circuit_breaker = (
    var.enable_deployment_circuit_breaker
  )

  database_url_secret_arn = module.langfuse_secrets.secret_arns["database_url"]
  salt_secret_arn         = module.langfuse_secrets.secret_arns["salt"]
  encryption_key_secret_arn = (
    module.langfuse_secrets.secret_arns["encryption_key"]
  )
  nextauth_secret_arn = module.langfuse_secrets.secret_arns["nextauth_secret"]
  clickhouse_url_secret_arn = (
    module.langfuse_secrets.secret_arns["clickhouse_url"]
  )
  clickhouse_migration_url_secret_arn = (
    module.langfuse_secrets.secret_arns["clickhouse_migration_url"]
  )
  redis_connection_string_secret_arn = (
    module.langfuse_secrets.secret_arns["redis_connection_string"]
  )
  init_user_email_secret_arn = (
    module.langfuse_secrets.secret_arns["init_user_email"]
  )
  init_user_name_secret_arn = (
    module.langfuse_secrets.secret_arns["init_user_name"]
  )
  init_user_password_secret_arn = (
    module.langfuse_secrets.secret_arns["init_user_password"]
  )
  init_project_public_key_secret_arn = (
    var.enable_langfuse_bootstrap_init
    ? data.aws_secretsmanager_secret.init_project_public_key[0].arn
    : ""
  )
  init_project_secret_key_secret_arn = (
    var.enable_langfuse_bootstrap_init
    ? data.aws_secretsmanager_secret.init_project_secret_key[0].arn
    : ""
  )
}

resource "aws_security_group_rule" "allow_langfuse_to_app_db" {
  count = var.enable_langfuse_compute ? 1 : 0

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = data.aws_security_group.app_db[0].id
  source_security_group_id = module.langfuse_compute[0].service_security_group_id
  description              = "Allow Langfuse services to app Postgres"
}

resource "aws_security_group_rule" "allow_langfuse_to_app_redis" {
  count = var.enable_langfuse_compute ? 1 : 0

  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = data.aws_security_group.app_redis[0].id
  source_security_group_id = module.langfuse_compute[0].service_security_group_id
  description              = "Allow Langfuse services to app Redis"
}

resource "aws_route53_record" "langfuse" {
  count = var.enable_langfuse_compute ? 1 : 0

  zone_id         = data.aws_route53_zone.selected.zone_id
  name            = local.effective_hostname
  type            = "A"
  allow_overwrite = true

  alias {
    name                   = module.langfuse_compute[0].alb_dns_name
    zone_id                = module.langfuse_compute[0].alb_zone_id
    evaluate_target_health = true
  }
}
