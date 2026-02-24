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
