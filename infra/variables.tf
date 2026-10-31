variable "region" {
  type    = string
  default = "eu-north-1"
}

variable "project_name" {
  type    = string
  default = "onetwothree"
}

variable "env" {
  type    = string
  default = "dev"
}

variable "google_client_id" {
  type      = string
  sensitive = true
  default   = ""
}

variable "google_client_secret" {
  type      = string
  sensitive = true
  default   = ""
}