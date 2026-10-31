terraform {
  required_version = ">= 1.10"

  cloud {
    organization = "ooad-2surfff"

    workspaces {
      name = "onetwothree-dev"
    }
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      PROJECT_NAME = var.project_name
      ManagedBy    = "terraform"
      Environment  = var.env
    }
  }
}