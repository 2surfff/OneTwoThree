resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-${var.env}-user-pool"

  auto_verified_attributes = ["email"]

  schema {
    attribute_data_type = "String"
    name                = "email"
    required            = true
    mutable             = true
  }

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "${var.project_name}-${var.env}-client"
  user_pool_id = aws_cognito_user_pool.main.id

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH"
  ]

  generate_secret = false
}

resource "aws_cognito_user_pool_domain" "domain" {
  domain       = "${var.project_name}-${var.env}-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}