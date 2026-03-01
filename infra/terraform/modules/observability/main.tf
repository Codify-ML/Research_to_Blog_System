locals {
  alb_name                  = substr("${var.name_prefix}-lf-alb", 0, 32)
  tg_name                   = substr("${var.name_prefix}-lf-web-tg", 0, 32)
  clickhouse_namespace_name = "${var.name_prefix}.internal"
  clickhouse_host = format(
    "clickhouse.%s",
    local.clickhouse_namespace_name
  )

  secret_arns = compact([
    var.database_url_secret_arn,
    var.salt_secret_arn,
    var.encryption_key_secret_arn,
    var.nextauth_secret_arn,
    var.clickhouse_url_secret_arn,
    var.clickhouse_migration_url_secret_arn,
    var.redis_connection_string_secret_arn,
    var.enable_bootstrap_init ? var.init_user_email_secret_arn : "",
    var.enable_bootstrap_init ? var.init_user_name_secret_arn : "",
    var.enable_bootstrap_init ? var.init_user_password_secret_arn : "",
    var.enable_bootstrap_init ? var.init_project_public_key_secret_arn : "",
    var.enable_bootstrap_init ? var.init_project_secret_key_secret_arn : "",
  ])

  bootstrap_environment = (
    var.enable_bootstrap_init
    ? concat(
      [
        {
          name  = "LANGFUSE_INIT_PROJECT_NAME"
          value = var.langfuse_init_project_name
        },
        {
          name  = "LANGFUSE_INIT_ORG_ID"
          value = var.langfuse_init_org_id
        },
      ],
      trimspace(var.langfuse_init_project_id) != ""
      ? [
        {
          name  = "LANGFUSE_INIT_PROJECT_ID"
          value = var.langfuse_init_project_id
        },
      ]
      : [],
    )
    : []
  )

  bootstrap_secrets = (
    var.enable_bootstrap_init
    ? [
      {
        name      = "LANGFUSE_INIT_USER_EMAIL"
        valueFrom = var.init_user_email_secret_arn
      },
      {
        name      = "LANGFUSE_INIT_USER_NAME"
        valueFrom = var.init_user_name_secret_arn
      },
      {
        name      = "LANGFUSE_INIT_USER_PASSWORD"
        valueFrom = var.init_user_password_secret_arn
      },
      {
        name      = "LANGFUSE_INIT_PROJECT_PUBLIC_KEY"
        valueFrom = var.init_project_public_key_secret_arn
      },
      {
        name      = "LANGFUSE_INIT_PROJECT_SECRET_KEY"
        valueFrom = var.init_project_secret_key_secret_arn
      },
    ]
    : []
  )

  common_environment = concat([
    {
      name  = "NEXTAUTH_URL"
      value = var.langfuse_public_url
    },
    {
      name  = "TELEMETRY_ENABLED"
      value = tostring(var.telemetry_enabled)
    },
    {
      name  = "AUTH_DISABLE_SIGNUP"
      value = tostring(var.auth_disable_signup)
    },
    {
      name  = "CLICKHOUSE_USER"
      value = var.clickhouse_user
    },
    {
      name  = "CLICKHOUSE_PASSWORD"
      value = var.clickhouse_password
    },
    {
      name  = "CLICKHOUSE_DB"
      value = var.clickhouse_db
    },
    {
      name  = "CLICKHOUSE_CLUSTER_ENABLED"
      value = tostring(var.clickhouse_cluster_enabled)
    },
    {
      name = "CLICKHOUSE_URL"
      value = format(
        "http://%s:%s@%s:8123",
        var.clickhouse_user,
        var.clickhouse_password,
        local.clickhouse_host
      )
    },
    {
      name = "CLICKHOUSE_MIGRATION_URL"
      value = format(
        "clickhouse://%s:%s@%s:9000",
        var.clickhouse_user,
        var.clickhouse_password,
        local.clickhouse_host
      )
    },
    {
      name  = "LANGFUSE_S3_EVENT_UPLOAD_BUCKET"
      value = var.s3_event_upload_bucket
    },
    {
      name  = "LANGFUSE_S3_EVENT_UPLOAD_REGION"
      value = var.s3_event_upload_region
    },
    {
      name  = "LANGFUSE_S3_MEDIA_UPLOAD_BUCKET"
      value = var.s3_media_upload_bucket
    },
    {
      name  = "LANGFUSE_S3_MEDIA_UPLOAD_REGION"
      value = var.s3_media_upload_region
    },
    {
      name  = "LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE"
      value = tostring(var.s3_force_path_style)
    },
    {
      name  = "LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE"
      value = tostring(var.s3_force_path_style)
    },
  ], local.bootstrap_environment)

  common_secrets = concat([
    {
      name      = "DATABASE_URL"
      valueFrom = var.database_url_secret_arn
    },
    {
      name      = "SALT"
      valueFrom = var.salt_secret_arn
    },
    {
      name      = "ENCRYPTION_KEY"
      valueFrom = var.encryption_key_secret_arn
    },
    {
      name      = "NEXTAUTH_SECRET"
      valueFrom = var.nextauth_secret_arn
    },
    {
      name      = "REDIS_CONNECTION_STRING"
      valueFrom = var.redis_connection_string_secret_arn
    },
  ], local.bootstrap_secrets)

  s3_bucket_arns = [
    "arn:aws:s3:::${var.s3_event_upload_bucket}",
    "arn:aws:s3:::${var.s3_media_upload_bucket}",
  ]
  s3_object_arns = [
    "arn:aws:s3:::${var.s3_event_upload_bucket}/*",
    "arn:aws:s3:::${var.s3_media_upload_bucket}/*",
  ]
}

check "bootstrap_init_inputs" {
  assert {
    condition = (
      !var.enable_bootstrap_init || (
        trimspace(var.langfuse_init_org_id) != ""
        && trimspace(var.init_user_email_secret_arn) != ""
        && trimspace(var.init_user_name_secret_arn) != ""
        && trimspace(var.init_user_password_secret_arn) != ""
        && trimspace(var.init_project_public_key_secret_arn) != ""
        && trimspace(var.init_project_secret_key_secret_arn) != ""
      )
    )
    error_message = "enable_bootstrap_init=true requires langfuse_init_org_id and init user/project key secret ARNs."
  }
}

resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-langfuse-alb-sg"
  description = "ALB security group for Langfuse ingress"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = var.alb_ingress_cidrs
    content {
      description = "Allow HTTPS from approved CIDR"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  dynamic "ingress" {
    for_each = var.alb_ingress_cidrs
    content {
      description = "Allow HTTP from approved CIDR"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "service" {
  name        = "${var.name_prefix}-langfuse-service-sg"
  description = "Langfuse service security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow ALB to reach Langfuse web"
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "clickhouse" {
  name        = "${var.name_prefix}-langfuse-clickhouse-sg"
  description = "Langfuse clickhouse service security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow Langfuse services to reach clickhouse HTTP"
    from_port       = 8123
    to_port         = 8123
    protocol        = "tcp"
    security_groups = [aws_security_group.service.id]
  }

  ingress {
    description     = "Allow Langfuse services to reach clickhouse TCP"
    from_port       = 9000
    to_port         = 9000
    protocol        = "tcp"
    security_groups = [aws_security_group.service.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "this" {
  name               = local.alb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "web" {
  name        = local.tg_name
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = var.enable_https ? "redirect" : "forward"

    dynamic "redirect" {
      for_each = var.enable_https ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "forward" {
      for_each = var.enable_https ? [] : [1]
      content {
        target_group {
          arn = aws_lb_target_group.web.arn
        }
      }
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  dynamic "default_action" {
    for_each = var.enable_auth ? [1] : []
    content {
      type = "authenticate-cognito"

      authenticate_cognito {
        user_pool_arn       = var.cognito_user_pool_arn
        user_pool_client_id = var.cognito_user_pool_client_id
        user_pool_domain    = var.cognito_user_pool_domain
      }
    }
  }

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

# Langfuse SDK and API clients must reach public API endpoints without Cognito redirects.
resource "aws_lb_listener_rule" "https_public_api" {
  count = var.enable_https ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }

  condition {
    path_pattern {
      values = ["/api/public", "/api/public/*"]
    }
  }
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-langfuse-cluster"
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${var.name_prefix}/langfuse-web"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.name_prefix}/langfuse-worker"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "clickhouse" {
  name              = "/ecs/${var.name_prefix}/langfuse-clickhouse"
  retention_in_days = var.log_retention_days
}

resource "aws_service_discovery_private_dns_namespace" "this" {
  name = local.clickhouse_namespace_name
  vpc  = var.vpc_id
}

resource "aws_service_discovery_service" "clickhouse" {
  name = "clickhouse"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.this.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }
}

resource "aws_iam_role" "execution" {
  name = "${var.name_prefix}-langfuse-task-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "${var.name_prefix}-langfuse-secrets-exec"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "kms:Decrypt",
        ]
        Resource = local.secret_arns
      },
    ]
  })
}

resource "aws_iam_role" "task" {
  name = "${var.name_prefix}-langfuse-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "task_secrets" {
  name = "${var.name_prefix}-langfuse-secrets-task"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "kms:Decrypt",
        ]
        Resource = local.secret_arns
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = local.s3_bucket_arns
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = local.s3_object_arns
      },
    ]
  })
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.name_prefix}-langfuse-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.web_cpu
  memory                   = var.web_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "langfuse-web"
      image     = var.langfuse_web_image
      essential = true
      portMappings = [{
        containerPort = 3000
        hostPort      = 3000
        protocol      = "tcp"
      }]
      environment = local.common_environment
      secrets     = local.common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.web.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-langfuse-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name        = "langfuse-worker"
      image       = var.langfuse_worker_image
      essential   = true
      environment = local.common_environment
      secrets     = local.common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "clickhouse" {
  family                   = "${var.name_prefix}-langfuse-clickhouse"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.clickhouse_cpu
  memory                   = var.clickhouse_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "clickhouse"
      image     = var.clickhouse_image
      essential = true
      portMappings = [
        {
          containerPort = 8123
          hostPort      = 8123
          protocol      = "tcp"
        },
        {
          containerPort = 9000
          hostPort      = 9000
          protocol      = "tcp"
        },
      ]
      environment = [
        {
          name  = "CLICKHOUSE_USER"
          value = var.clickhouse_user
        },
        {
          name  = "CLICKHOUSE_PASSWORD"
          value = var.clickhouse_password
        },
        {
          name  = "CLICKHOUSE_DB"
          value = var.clickhouse_db
        },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.clickhouse.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "web" {
  name                               = "${var.name_prefix}-langfuse-web"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.web.arn
  desired_count                      = var.web_desired_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent

  dynamic "deployment_circuit_breaker" {
    for_each = var.enable_deployment_circuit_breaker ? [1] : []
    content {
      enable   = true
      rollback = true
    }
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "langfuse-web"
    container_port   = 3000
  }

  depends_on = [aws_ecs_service.clickhouse]
}

resource "aws_ecs_service" "worker" {
  name                               = "${var.name_prefix}-langfuse-worker"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.worker.arn
  desired_count                      = var.worker_desired_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent

  dynamic "deployment_circuit_breaker" {
    for_each = var.enable_deployment_circuit_breaker ? [1] : []
    content {
      enable   = true
      rollback = true
    }
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }

  depends_on = [aws_ecs_service.clickhouse]
}

resource "aws_ecs_service" "clickhouse" {
  name                               = "${var.name_prefix}-langfuse-clickhouse"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.clickhouse.arn
  desired_count                      = var.clickhouse_desired_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent

  dynamic "deployment_circuit_breaker" {
    for_each = var.enable_deployment_circuit_breaker ? [1] : []
    content {
      enable   = true
      rollback = true
    }
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.clickhouse.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.clickhouse.arn
  }
}

data "aws_region" "current" {}
