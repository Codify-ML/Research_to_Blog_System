variable "name_prefix" {
  description = "Prefix used for secret names."
  type        = string
}

variable "openai_api_key" {
  description = "Optional initial OpenAI API key secret value."
  type        = string
  default     = ""
  sensitive   = true
}

variable "api_auth_key" {
  description = "Optional initial API shared key secret value."
  type        = string
  default     = ""
  sensitive   = true
}
