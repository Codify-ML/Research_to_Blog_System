locals {
  legacy_db_url = format(
    "postgresql://%s:%s@%s:%d/%s",
    var.db_username,
    var.db_password,
    var.db_endpoint,
    var.db_port,
    var.db_name,
  )
  redis_base_url = format("redis://%s:%d", var.redis_endpoint, var.redis_port)
  openai_secret = var.openai_secret_arn != "" ? [{
    name      = "OPENAI_API_KEY"
    valueFrom = var.openai_secret_arn
  }] : []
  api_auth_secret = var.api_auth_secret_arn != "" ? [{
    name      = "API_AUTH_KEY"
    valueFrom = var.api_auth_secret_arn
  }] : []
  db_password_secret = var.db_secret_arn != "" ? [{
    name      = "DB_PASSWORD"
    valueFrom = "${var.db_secret_arn}:password::"
  }] : []
  db_connection_environment = var.db_secret_arn != "" ? [
    { name = "DB_HOST", value = var.db_endpoint },
    { name = "DB_PORT", value = tostring(var.db_port) },
    { name = "DB_NAME", value = var.db_name },
    { name = "DB_USER", value = var.db_username },
    ] : [
    { name = "DATABASE_URL", value = local.legacy_db_url },
  ]
  api_environment = concat([
    { name = "USE_MOCK_LLM", value = tostring(var.use_mock_llm) },
    { name = "MOCK_MODE_STRICT", value = tostring(var.mock_mode_strict) },
    { name = "API_AUTH_ENABLED", value = tostring(var.api_auth_enabled) },
    {
      name  = "OPENAI_MODEL_RESEARCHER"
      value = var.openai_model_researcher
    },
    { name = "OPENAI_MODEL_WRITER", value = var.openai_model_writer },
    { name = "OPENAI_MODEL_EDITOR", value = var.openai_model_editor },
    { name = "JOB_STORE_BACKEND", value = "postgres" },
    { name = "REDIS_URL", value = "${local.redis_base_url}/0" },
    { name = "CELERY_BROKER_URL", value = "${local.redis_base_url}/0" },
    {
      name  = "CELERY_RESULT_BACKEND"
      value = "${local.redis_base_url}/1"
    },
  ], local.db_connection_environment)
  worker_environment = local.api_environment
  ui_environment = [
    { name = "UI_API_BASE_URL", value = var.api_base_url },
    { name = "UI_POLL_INTERVAL_SECONDS", value = "1.0" },
    { name = "UI_REQUEST_TIMEOUT_SECONDS", value = "10.0" },
    { name = "API_AUTH_ENABLED", value = tostring(var.api_auth_enabled) },
    {
      name  = "UI_COGNITO_HOSTED_UI_BASE"
      value = var.ui_cognito_hosted_ui_base
    },
    {
      name  = "UI_COGNITO_CLIENT_ID"
      value = var.ui_cognito_user_pool_client_id
    },
    { name = "UI_PUBLIC_BASE_URL", value = var.ui_public_base_url },
  ]
  ui_logout_environment = [
    {
      name  = "UI_COGNITO_HOSTED_UI_BASE"
      value = var.ui_cognito_hosted_ui_base
    },
    {
      name  = "UI_COGNITO_CLIENT_ID"
      value = var.ui_cognito_user_pool_client_id
    },
    { name = "UI_PUBLIC_BASE_URL", value = var.ui_public_base_url },
  ]
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name_prefix}/api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.name_prefix}/worker"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "ui" {
  name              = "/ecs/${var.name_prefix}/ui"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "ui_logout" {
  name              = "/ecs/${var.name_prefix}/ui-logout"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"
}

resource "aws_lb" "api" {
  name               = "${var.name_prefix}-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_api_sg_id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb" "ui" {
  name               = "${var.name_prefix}-ui-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_ui_sg_id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name_prefix}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }
}

resource "aws_lb_target_group" "ui" {
  name        = "${var.name_prefix}-ui-tg"
  port        = 8501
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/_stcore/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }
}

resource "aws_lb_target_group" "ui_logout" {
  name        = "${var.name_prefix}-ui-lo-tg"
  port        = 8600
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }
}

resource "aws_lb_listener" "api_http" {
  load_balancer_arn = aws_lb.api.arn
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
          arn = aws_lb_target_group.api.arn
        }
      }
    }
  }
}

resource "aws_lb_listener" "api_https" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "ui_http" {
  load_balancer_arn = aws_lb.ui.arn
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
          arn = aws_lb_target_group.ui.arn
        }
      }
    }
  }
}

resource "aws_lb_listener" "ui_https" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.ui.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  dynamic "default_action" {
    for_each = var.enable_ui_auth ? [1] : []
    content {
      type = "authenticate-cognito"

      authenticate_cognito {
        user_pool_arn       = var.ui_cognito_user_pool_arn
        user_pool_client_id = var.ui_cognito_user_pool_client_id
        user_pool_domain    = var.ui_cognito_user_pool_domain
      }
    }
  }

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ui.arn
  }
}

resource "aws_lb_listener_rule" "ui_logout_https" {
  count = var.enable_https ? 1 : 0

  listener_arn = aws_lb_listener.ui_https[0].arn
  priority     = 5

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ui_logout.arn
  }

  condition {
    path_pattern {
      values = ["/auth/logout"]
    }
  }
}

resource "aws_lb_listener_rule" "ui_logout_http" {
  count = var.enable_https ? 0 : 1

  listener_arn = aws_lb_listener.ui_http.arn
  priority     = 5

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ui_logout.arn
  }

  condition {
    path_pattern {
      values = ["/auth/logout"]
    }
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [{
        containerPort = 8000
        hostPort      = 8000
        protocol      = "tcp"
      }]
      environment = local.api_environment
      secrets = concat(
        local.openai_secret,
        local.api_auth_secret,
        local.db_password_secret,
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name        = "worker"
      image       = var.worker_image
      essential   = true
      environment = local.worker_environment
      secrets = concat(
        local.openai_secret,
        local.api_auth_secret,
        local.db_password_secret,
      )
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

resource "aws_ecs_task_definition" "ui" {
  family                   = "${var.name_prefix}-ui"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "ui"
      image     = var.ui_image
      essential = true
      portMappings = [{
        containerPort = 8501
        hostPort      = 8501
        protocol      = "tcp"
      }]
      environment = local.ui_environment
      secrets     = local.api_auth_secret
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ui.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "ui_logout" {
  family                   = "${var.name_prefix}-ui-logout"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "ui-logout"
      image     = var.ui_image
      essential = true
      command = [
        "uv",
        "run",
        "uvicorn",
        "apps.ui.logout_app:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8600",
      ]
      portMappings = [{
        containerPort = 8600
        hostPort      = 8600
        protocol      = "tcp"
      }]
      environment = local.ui_logout_environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ui_logout.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name                               = "${var.name_prefix}-api"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.api_desired_count
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
    security_groups  = [var.api_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
}

resource "aws_ecs_service" "worker" {
  name                               = "${var.name_prefix}-worker"
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
    security_groups  = [var.worker_sg_id]
    assign_public_ip = false
  }
}

resource "aws_ecs_service" "ui" {
  name                               = "${var.name_prefix}-ui"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.ui.arn
  desired_count                      = var.ui_desired_count
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
    security_groups  = [var.ui_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ui.arn
    container_name   = "ui"
    container_port   = 8501
  }
}

resource "aws_ecs_service" "ui_logout" {
  name                               = "${var.name_prefix}-ui-logout"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.ui_logout.arn
  desired_count                      = var.ui_logout_desired_count
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
    security_groups  = [var.ui_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ui_logout.arn
    container_name   = "ui-logout"
    container_port   = 8600
  }
}

data "aws_region" "current" {}
