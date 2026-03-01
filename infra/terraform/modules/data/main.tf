resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.name_prefix}-db-subnets"
  }
}

resource "aws_db_instance" "postgres" {
  identifier                   = "${var.name_prefix}-postgres"
  engine                       = "postgres"
  instance_class               = var.db_instance_class
  allocated_storage            = var.db_allocated_storage
  db_name                      = var.db_name
  username                     = var.db_username
  manage_master_user_password  = true
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = [var.db_sg_id]
  backup_retention_period      = 7
  deletion_protection          = false
  skip_final_snapshot          = true
  publicly_accessible          = false
  auto_minor_version_upgrade   = true
  apply_immediately            = true
  storage_encrypted            = true
  performance_insights_enabled = false

  tags = {
    Name = "${var.name_prefix}-postgres"
  }
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-redis-subnets"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_parameter_group" "redis" {
  name   = "${var.name_prefix}-redis-params"
  family = var.redis_parameter_group_family

  parameter {
    name  = "maxmemory-policy"
    value = var.redis_maxmemory_policy
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.name_prefix}-redis"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [var.redis_sg_id]
  port                 = 6379

  tags = {
    Name = "${var.name_prefix}-redis"
  }
}
