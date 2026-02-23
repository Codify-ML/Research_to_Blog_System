variable "name_prefix" {
  description = "Prefix used for data resource names."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for data stores."
  type        = list(string)
}

variable "db_sg_id" {
  description = "Security group ID for Postgres."
  type        = string
}

variable "redis_sg_id" {
  description = "Security group ID for Redis."
  type        = string
}

variable "db_name" {
  description = "Postgres database name."
  type        = string
}

variable "db_username" {
  description = "Postgres username."
  type        = string
}

variable "db_password" {
  description = "Postgres password."
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class for Postgres."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS Postgres."
  type        = number
  default     = 20
}

variable "redis_node_type" {
  description = "ElastiCache node type for Redis."
  type        = string
  default     = "cache.t4g.micro"
}
