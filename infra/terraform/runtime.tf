data "aws_caller_identity" "current" {}

resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  description = "Public HTTPS ingress"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  name_prefix = "${local.name_prefix}-app-"
  description = "ECS application tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "API from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  ingress {
    description     = "Frontend from ALB"
    from_port       = 8080
    to_port         = 8080
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

resource "aws_security_group" "data" {
  name_prefix = "${local.name_prefix}-data-"
  description = "Managed data stores"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  ingress {
    description     = "Redis from ECS"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

resource "aws_db_subnet_group" "main" {
  name       = local.name_prefix
  subnet_ids = values(aws_subnet.data)[*].id
}

resource "aws_db_instance" "main" {
  identifier                      = local.name_prefix
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = var.database_instance_class
  allocated_storage               = 20
  max_allocated_storage           = 100
  storage_type                    = "gp3"
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.platform.arn
  db_name                         = "cloudwise"
  username                        = "cloudwise"
  password                        = var.database_password
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.data.id]
  multi_az                        = var.environment == "production"
  publicly_accessible             = false
  backup_retention_period         = var.environment == "production" ? 14 : 7
  deletion_protection             = var.environment == "production"
  skip_final_snapshot             = var.environment != "production"
  final_snapshot_identifier       = var.environment == "production" ? "${local.name_prefix}-final" : null
  performance_insights_enabled    = true
  auto_minor_version_upgrade      = true
  apply_immediately               = false
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name_prefix
  subnet_ids = values(aws_subnet.data)[*].id
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = local.name_prefix
  description                = "CloudWise ${var.environment} task broker"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.redis_node_type
  port                       = 6379
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.data.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token
  snapshot_retention_limit   = 7
  apply_immediately          = false
}

resource "aws_secretsmanager_secret" "runtime" {
  name                    = "${local.name_prefix}/runtime"
  kms_key_id              = aws_kms_key.platform.arn
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret_version" "runtime" {
  secret_id = aws_secretsmanager_secret.runtime.id
  secret_string = jsonencode({
    database_url               = "postgresql+asyncpg://cloudwise:${var.database_password}@${aws_db_instance.main.address}:5432/cloudwise?ssl=require"
    redis_url                  = "rediss://:${var.redis_auth_token}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
    auth_secret_key            = var.auth_secret_key
    external_id_encryption_key = var.external_id_encryption_key
  })
}

resource "aws_ecs_cluster" "main" {
  name = local.name_prefix
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "ecs_execution" {
  name = "${local.name_prefix}-ecs-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "runtime-secrets"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue", "kms:Decrypt"]
      Resource = [aws_secretsmanager_secret.runtime.arn, aws_kms_key.platform.arn]
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "application"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.reports.arn}/*" },
      { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey"], Resource = aws_kms_key.platform.arn },
      { Effect = "Allow", Action = ["pricing:GetProducts"], Resource = "*" },
      { Effect = "Allow", Action = ["sts:AssumeRole"], Resource = "arn:aws:iam::*:role/CloudWise*" }
    ]
  })
}

locals {
  runtime_environment = [
    { name = "CLOUDWISE_ENVIRONMENT", value = var.environment },
    { name = "CLOUDWISE_CORS_ORIGINS", value = jsonencode(["https://${var.domain_name}"]) },
    { name = "CLOUDWISE_RECOMMENDATION_PRICING_PROVIDER", value = "aws" },
    { name = "CLOUDWISE_REPORT_STORAGE_PROVIDER", value = "s3" },
    { name = "CLOUDWISE_REPORT_S3_BUCKET", value = aws_s3_bucket.reports.id }
  ]
  runtime_secrets = [
    { name = "CLOUDWISE_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:database_url::" },
    { name = "CLOUDWISE_REDIS_URL", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:redis_url::" },
    { name = "CLOUDWISE_AUTH_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:auth_secret_key::" },
    { name = "CLOUDWISE_EXTERNAL_ID_ENCRYPTION_KEY", valueFrom = "${aws_secretsmanager_secret.runtime.arn}:external_id_encryption_key::" }
  ]
  backend_image  = "${aws_ecr_repository.service["backend"].repository_url}:${var.backend_image_tag}"
  frontend_image = "${aws_ecr_repository.service["frontend"].repository_url}:${var.frontend_image_tag}"
}

resource "aws_ecs_task_definition" "backend" {
  for_each = {
    api       = ["uvicorn", "cloudwise.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
    worker    = ["celery", "-A", "cloudwise.worker:celery_app", "worker", "--loglevel=INFO", "--concurrency=2"]
    scheduler = ["celery", "-A", "cloudwise.worker:celery_app", "beat", "--loglevel=INFO", "--schedule=/tmp/celerybeat-schedule"]
  }

  family                   = "${local.name_prefix}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.key == "worker" ? 1024 : 512
  memory                   = each.key == "worker" ? 2048 : 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name         = each.key
    image        = local.backend_image
    command      = each.value
    essential    = true
    environment  = local.runtime_environment
    secrets      = local.runtime_secrets
    portMappings = each.key == "api" ? [{ containerPort = 8000, protocol = "tcp" }] : []
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name_prefix}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  container_definitions = jsonencode([{
    name         = "frontend"
    image        = local.frontend_image
    essential    = true
    portMappings = [{ containerPort = 8080, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service["frontend"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

resource "aws_lb" "main" {
  name                       = local.name_prefix
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = values(aws_subnet.public)[*].id
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name_prefix}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check { path = "/api/v1/health/live" }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${local.name_prefix}-web"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check { path = "/healthz" }
}

resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}

resource "aws_route53_record" "certificate" {
  for_each = { for option in aws_acm_certificate.main.domain_validation_options : option.domain_name => option }
  zone_id  = var.route53_zone_id
  name     = each.value.resource_record_name
  type     = each.value.resource_record_type
  records  = [each.value.resource_record_value]
  ttl      = 60
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.certificate : record.fqdn]
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

resource "aws_route53_record" "application" {
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

resource "aws_ecs_service" "backend" {
  for_each = { api = var.api_desired_count, worker = 1, scheduler = 1 }

  name                  = "${local.name_prefix}-${each.key}"
  cluster               = aws_ecs_cluster.main.id
  task_definition       = aws_ecs_task_definition.backend[each.key].arn
  desired_count         = each.value
  launch_type           = "FARGATE"
  wait_for_steady_state = true
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = values(aws_subnet.private)[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }
  dynamic "load_balancer" {
    for_each = each.key == "api" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.api.arn
      container_name   = "api"
      container_port   = 8000
    }
  }
  depends_on = [aws_lb_listener.https, aws_iam_role_policy.ecs_execution_secrets]

  lifecycle {
    ignore_changes = [task_definition]
  }
}

resource "aws_ecs_service" "frontend" {
  name                  = "${local.name_prefix}-frontend"
  cluster               = aws_ecs_cluster.main.id
  task_definition       = aws_ecs_task_definition.frontend.arn
  desired_count         = var.frontend_desired_count
  launch_type           = "FARGATE"
  wait_for_steady_state = true
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = values(aws_subnet.private)[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 8080
  }
  depends_on = [aws_lb_listener.https]

  lifecycle {
    ignore_changes = [task_definition]
  }
}
