variable "name_prefix" {
  description = "Prefix used for Langfuse secret names."
  type        = string
}

variable "secret_names" {
  description = "Set of secret keys to provision under name_prefix."
  type        = set(string)
}
