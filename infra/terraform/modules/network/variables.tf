variable "name_prefix" {
  description = "Prefix used for networking resource names."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR range for the VPC."
  type        = string
}

variable "az_count" {
  description = "Number of Availability Zones to spread across."
  type        = number
  default     = 2
}

variable "enable_nat_gateway" {
  description = "Whether to create a single NAT gateway for private egress."
  type        = bool
  default     = false
}
