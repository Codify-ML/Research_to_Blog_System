variable "name_prefix" {
  description = "Prefix used for ECR repository names."
  type        = string
}

variable "image_mutability" {
  description = "Tag mutability policy for ECR repositories."
  type        = string
  default     = "MUTABLE"
}

variable "scan_on_push" {
  description = "Whether to scan pushed images for vulnerabilities."
  type        = bool
  default     = true
}

variable "image_retention_count" {
  description = "Number of most recent images to retain per repository."
  type        = number
  default     = 10

  validation {
    condition     = var.image_retention_count >= 1
    error_message = "image_retention_count must be at least 1."
  }
}
