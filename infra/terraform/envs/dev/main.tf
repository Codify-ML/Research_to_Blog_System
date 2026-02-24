locals {
  name_prefix   = "${var.project_name}-${var.environment}"
  secret_prefix = "${var.project_name}/${var.environment}"
}

data "aws_route53_zone" "selected" {
  zone_id = var.route53_zone_id
}

data "aws_caller_identity" "current" {}

module "network" {
  source = "../../modules/network"

  name_prefix        = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  az_count           = var.az_count
  enable_nat_gateway = var.enable_nat_gateway
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix    = local.secret_prefix
  openai_api_key = var.openai_api_key
  api_auth_key   = var.api_auth_key
}

module "ecr" {
  source = "../../modules/ecr"

  name_prefix = local.name_prefix
}

resource "aws_acm_certificate" "app" {
  domain_name               = var.ui_hostname
  subject_alternative_names = [var.api_hostname]
  validation_method         = "DNS"
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.app.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id = data.aws_route53_zone.selected.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "app" {
  certificate_arn         = aws_acm_certificate.app.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

resource "aws_cognito_user_pool" "ui" {
  name = "${local.name_prefix}-users"

  auto_verified_attributes = ["email"]

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  username_attributes = ["email"]

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }
}

resource "aws_cognito_user_pool_client" "ui" {
  name         = "${local.name_prefix}-ui-client"
  user_pool_id = aws_cognito_user_pool.ui.id

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["https://${var.ui_hostname}/oauth2/idpresponse"]
  logout_urls                          = ["https://${var.ui_hostname}/"]
  supported_identity_providers         = ["COGNITO"]

  generate_secret = true
}

resource "aws_cognito_user_pool_domain" "ui" {
  domain       = "${var.cognito_domain_prefix}-${substr(data.aws_caller_identity.current.account_id, 6, 6)}"
  user_pool_id = aws_cognito_user_pool.ui.id
}

module "security" {
  source = "../../modules/security"

  name_prefix         = local.name_prefix
  vpc_id              = module.network.vpc_id
  openai_secret_arn   = module.secrets.openai_secret_arn
  api_auth_secret_arn = module.secrets.api_auth_secret_arn
}

module "data" {
  source = "../../modules/data"

  name_prefix          = local.name_prefix
  private_subnet_ids   = module.network.private_subnet_ids
  db_sg_id             = module.security.db_sg_id
  redis_sg_id          = module.security.redis_sg_id
  db_name              = var.db_name
  db_username          = var.db_username
  db_instance_class    = var.db_instance_class
  db_allocated_storage = var.db_allocated_storage
  redis_node_type      = var.redis_node_type
}

resource "aws_iam_role_policy" "task_db_secret" {
  count = module.data.db_master_secret_arn != "" ? 1 : 0

  name = "${local.name_prefix}-db-secret-access"
  role = module.security.task_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = module.data.db_master_secret_arn
      },
    ]
  })
}

resource "aws_iam_role_policy" "task_execution_db_secret" {
  count = module.data.db_master_secret_arn != "" ? 1 : 0

  name = "${local.name_prefix}-db-secret-access-exec"
  role = module.security.task_execution_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = module.data.db_master_secret_arn
      },
    ]
  })
}

module "compute" {
  source = "../../modules/compute"

  name_prefix                    = local.name_prefix
  vpc_id                         = module.network.vpc_id
  public_subnet_ids              = module.network.public_subnet_ids
  private_subnet_ids             = module.network.private_subnet_ids
  alb_api_sg_id                  = module.security.alb_api_sg_id
  alb_ui_sg_id                   = module.security.alb_ui_sg_id
  api_sg_id                      = module.security.api_sg_id
  ui_sg_id                       = module.security.ui_sg_id
  worker_sg_id                   = module.security.worker_sg_id
  task_execution_role_arn        = module.security.task_execution_role_arn
  task_role_arn                  = module.security.task_role_arn
  db_endpoint                    = module.data.db_endpoint
  db_port                        = module.data.db_port
  db_name                        = var.db_name
  db_username                    = var.db_username
  db_password                    = var.db_password
  db_secret_arn                  = module.data.db_master_secret_arn
  redis_endpoint                 = module.data.redis_endpoint
  redis_port                     = module.data.redis_port
  openai_secret_arn              = module.secrets.openai_secret_arn
  api_auth_secret_arn            = module.secrets.api_auth_secret_arn
  api_image                      = var.api_image != "" ? var.api_image : "${module.ecr.api_repository_url}:${var.image_tag}"
  worker_image                   = var.worker_image != "" ? var.worker_image : "${module.ecr.worker_repository_url}:${var.image_tag}"
  ui_image                       = var.ui_image != "" ? var.ui_image : "${module.ecr.ui_repository_url}:${var.image_tag}"
  api_base_url                   = var.enable_https ? "https://${var.api_hostname}" : "http://${var.api_hostname}"
  api_auth_enabled               = var.api_auth_enabled
  use_mock_llm                   = var.use_mock_llm
  mock_mode_strict               = var.mock_mode_strict
  openai_model_researcher        = var.openai_model_researcher
  openai_model_writer            = var.openai_model_writer
  openai_model_editor            = var.openai_model_editor
  ui_cognito_hosted_ui_base      = "https://${aws_cognito_user_pool_domain.ui.domain}.auth.${var.aws_region}.amazoncognito.com"
  ui_public_base_url             = var.enable_https ? "https://${var.ui_hostname}" : "http://${var.ui_hostname}"
  enable_https                   = var.enable_https
  certificate_arn                = aws_acm_certificate_validation.app.certificate_arn
  enable_ui_auth                 = var.enable_ui_auth
  ui_cognito_user_pool_arn       = aws_cognito_user_pool.ui.arn
  ui_cognito_user_pool_client_id = aws_cognito_user_pool_client.ui.id
  ui_cognito_user_pool_domain    = aws_cognito_user_pool_domain.ui.domain
}

resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = var.api_hostname
  type    = "A"

  alias {
    name                   = module.compute.api_alb_dns_name
    zone_id                = module.compute.api_alb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "ui" {
  zone_id = data.aws_route53_zone.selected.zone_id
  name    = var.ui_hostname
  type    = "A"

  alias {
    name                   = module.compute.ui_alb_dns_name
    zone_id                = module.compute.ui_alb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_wafv2_web_acl" "edge" {
  name  = "${local.name_prefix}-edge-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedCommon"
    priority = 1

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    override_action {
      none {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "awsManagedCommon"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedKnownBadInputs"
    priority = 2

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    override_action {
      none {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "awsManagedBadInputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimitPerIP"
    priority = 3

    action {
      block {}
    }

    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = var.waf_rate_limit
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "rateLimitPerIp"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${replace(local.name_prefix, "-", "")}-edge-waf"
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = module.compute.api_alb_arn
  web_acl_arn  = aws_wafv2_web_acl.edge.arn
}

resource "aws_wafv2_web_acl_association" "ui" {
  resource_arn = module.compute.ui_alb_arn
  web_acl_arn  = aws_wafv2_web_acl.edge.arn
}
