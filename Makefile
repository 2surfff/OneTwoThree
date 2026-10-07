# ============================================================================
# Meetings App — ECS Fargate & Cognito deployment contract (Makefile)
# Usage:  make aws-deploy-auth     (deploy Cognito User Pool & Google IdP)
#         make aws-deploy-frontend (build frontend with Cognito config, sync to S3, invalidate CloudFront)
#         make deploy-frontend     (alias for aws-deploy-frontend, runs auth first)
#         make deploy-backend      (ECR login, Docker build, push, ECS redeploy)
#         make deploy-infra        (one-time: create all AWS resources)
#         make deploy-all          (full deployment pipeline: auth -> frontend -> backend)
# ============================================================================
.DEFAULT_GOAL := help

# Load environment variables from .env if present
-include .env
export

# ---------------------------------------------------------------------------
# Configuration (override via environment or command line)
# ---------------------------------------------------------------------------
AWS_REGION            ?= eu-north-1
AWS_ACCOUNT_ID        ?= 334177992228
PROJECT               ?= meetings
FRONTEND_DOMAIN       ?= d1y19dbl226ufk.cloudfront.net

# Auth (Cognito & Google OAuth)
AUTH_STACK            ?= $(PROJECT)-auth
GOOGLE_CLIENT_ID      ?=
GOOGLE_CLIENT_SECRET  ?=
COGNITO_DOMAIN_PREFIX ?= anton-meetings-2026

# Frontend
S3_BUCKET             ?= $(PROJECT)-frontend-$(AWS_ACCOUNT_ID)
CF_DISTRIBUTION_ID    ?= ESXCTSSJ27R0H

# Backend
ECR_REPO              ?= $(PROJECT)-backend
ECR_URI               ?= $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO)
ECS_CLUSTER           ?= $(PROJECT)-cluster
ECS_SERVICE           ?= $(PROJECT)-backend-svc
ECS_TASK_FAMILY       ?= $(PROJECT)-backend-task

# Network (default VPC)
VPC_ID                ?= vpc-06a44a341230eac1f
SUBNET_1              ?= subnet-04f8a8ab3ddd48bca
SUBNET_2              ?= subnet-051036efda8009e98
ALB_SG                ?= sg-06257b3ed60d576f7
ECS_SG                ?= sg-03ae0158551fe30b0
TG_ARN                ?= arn:aws:elasticloadbalancing:eu-north-1:334177992228:targetgroup/meetings-backend-tg/71809a34245ffbb2

# Commit SHA for image tagging
TAG                   ?= $(shell git rev-parse --short HEAD)

##@ Auth Deployment

.PHONY: aws-deploy-auth deploy-auth
aws-deploy-auth deploy-auth: ## Deploy Cognito User Pool, Google IdP, Managed Login v2
	@echo "==> Deploying Cognito Auth stack ($(AUTH_STACK))..."
	aws cloudformation deploy \
	  --template-file infra/auth.yml \
	  --stack-name $(AUTH_STACK) \
	  --parameter-overrides \
	    ProjectName=$(PROJECT) \
	    GoogleClientId="$(GOOGLE_CLIENT_ID)" \
	    GoogleClientSecret="$(GOOGLE_CLIENT_SECRET)" \
	    CognitoDomainPrefix="$(COGNITO_DOMAIN_PREFIX)" \
	    FrontendDomain="$(FRONTEND_DOMAIN)" \
	  --capabilities CAPABILITY_IAM \
	  --no-fail-on-empty-changeset \
	  --region $(AWS_REGION)
	@echo "==> Cognito Auth stack deployed!"

# Cognito Stack Outputs
USER_POOL_ID          ?= eu-north-1_2JHnz3607
USER_POOL_CLIENT_ID   ?= 520q7rcdd0c5hf0ahk2adb8bm3
COGNITO_DOMAIN        ?= anton-meetings-2026.auth.eu-north-1.amazoncognito.com
COGNITO_AUTHORITY     ?= https://cognito-idp.eu-north-1.amazonaws.com/eu-north-1_2JHnz3607

##@ Frontend Deployment

.PHONY: aws-deploy-frontend deploy-frontend
aws-deploy-frontend deploy-frontend: aws-deploy-auth ## Build frontend with Cognito config, sync to S3, invalidate CloudFront
	@echo "==> Setting frontend Cognito configuration..."
	@echo "UserPoolId:   $(USER_POOL_ID)"
	@echo "ClientId:     $(USER_POOL_CLIENT_ID)"
	@echo "AuthDomain:   $(COGNITO_DOMAIN)"
	@echo "AuthorityUrl: $(COGNITO_AUTHORITY)"
	@node -e "const fs=require('fs'); fs.writeFileSync('front/.env.production', 'VITE_COGNITO_REGION=$(AWS_REGION)\nVITE_COGNITO_USER_POOL_ID=$(USER_POOL_ID)\nVITE_COGNITO_CLIENT_ID=$(USER_POOL_CLIENT_ID)\nVITE_COGNITO_DOMAIN=$(COGNITO_DOMAIN)\nVITE_COGNITO_AUTHORITY=$(COGNITO_AUTHORITY)\nVITE_COGNITO_GOOGLE=true\nVITE_API_URL=\n');"
	@echo "==> Building frontend..."
	cd front && npm run build
	@echo "==> Syncing to S3 bucket $(S3_BUCKET)..."
	aws s3 sync front/dist "s3://$(S3_BUCKET)" --delete --region $(AWS_REGION)
	@echo "==> Creating CloudFront invalidation..."
	aws cloudfront create-invalidation \
	  --distribution-id $(CF_DISTRIBUTION_ID) --paths "/*" \
	  --query "Invalidation.Status" --output text
	@echo "==> Frontend deployed!"

##@ Backend Deployment

.PHONY: deploy-backend
deploy-backend: ## Login to ECR, build Docker image, push with commit SHA tag, update ECS
	@echo "==> Logging into ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | \
	  docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	@echo "==> Building Docker image (tag: $(TAG))..."
	docker build -t $(ECR_URI):$(TAG) -f back/Dockerfile back/
	@echo "==> Pushing image to ECR..."
	docker push $(ECR_URI):$(TAG)
	@echo "==> Updating ECS service (force new deployment)..."
	aws ecs update-service \
	  --cluster $(ECS_CLUSTER) --service $(ECS_SERVICE) \
	  --force-new-deployment --region $(AWS_REGION) \
	  --query "service.deployments[0].status" --output text
	@echo "==> Backend deployed with image tag $(TAG)!"

##@ Pipeline

.PHONY: deploy-all
deploy-all: aws-deploy-auth aws-deploy-frontend deploy-backend ## Full deployment pipeline: auth -> frontend -> backend

##@ Infrastructure (one-time setup)

.PHONY: deploy-infra
deploy-infra: infra-ecr infra-s3 infra-cloudfront infra-security-groups infra-alb infra-ecs ## Create all AWS infrastructure

.PHONY: infra-ecr
infra-ecr: ## Create ECR repository
	aws ecr create-repository --repository-name $(ECR_REPO) \
	  --region $(AWS_REGION) --image-scanning-configuration scanOnPush=true

.PHONY: infra-s3
infra-s3: ## Create private S3 bucket for frontend
	aws s3api create-bucket --bucket $(S3_BUCKET) --region $(AWS_REGION) \
	  --create-bucket-configuration LocationConstraint=$(AWS_REGION)
	aws s3api put-public-access-block --bucket $(S3_BUCKET) \
	  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

.PHONY: infra-cloudfront
infra-cloudfront: ## Create CloudFront distribution with OAC
	aws cloudfront create-origin-access-control \
	  --origin-access-control-config "Name=$(PROJECT)-frontend-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3"
	aws cloudfront create-distribution --distribution-config file://infra/cf-distribution.json

.PHONY: infra-security-groups
infra-security-groups: ## Create ALB and ECS security groups
	aws ec2 create-security-group --group-name $(PROJECT)-alb-sg \
	  --description "ALB - HTTP 80" --vpc-id $(VPC_ID) --region $(AWS_REGION)
	aws ec2 authorize-security-group-ingress --group-id $(ALB_SG) \
	  --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $(AWS_REGION)
	aws ec2 create-security-group --group-name $(PROJECT)-ecs-sg \
	  --description "ECS - traffic from ALB only" --vpc-id $(VPC_ID) --region $(AWS_REGION)
	aws ec2 authorize-security-group-ingress --group-id $(ECS_SG) \
	  --protocol tcp --port 8000 --source-group $(ALB_SG) --region $(AWS_REGION)

.PHONY: infra-alb
infra-alb: ## Create ALB, Target Group, and Listener
	aws elbv2 create-load-balancer --name $(PROJECT)-alb \
	  --subnets $(SUBNET_1) $(SUBNET_2) --security-groups $(ALB_SG) \
	  --scheme internet-facing --type application --region $(AWS_REGION)
	aws elbv2 create-target-group --name $(PROJECT)-backend-tg \
	  --protocol HTTP --port 8000 --vpc-id $(VPC_ID) --target-type ip \
	  --health-check-path /api/health --region $(AWS_REGION)
	aws elbv2 create-listener --load-balancer-arn $$(aws elbv2 describe-load-balancers \
	    --names $(PROJECT)-alb --query "LoadBalancers[0].LoadBalancerArn" --output text --region $(AWS_REGION)) \
	  --protocol HTTP --port 80 --default-actions "Type=forward,TargetGroupArn=$(TG_ARN)" --region $(AWS_REGION)

.PHONY: infra-ecs
infra-ecs: ## Create ECS Cluster, Task Definition, and Service
	aws ecs create-cluster --cluster-name $(ECS_CLUSTER) --region $(AWS_REGION)
	aws ecs register-task-definition --cli-input-json file://infra/task-definition.json --region $(AWS_REGION)
	aws ecs create-service --cluster $(ECS_CLUSTER) --service-name $(ECS_SERVICE) \
	  --task-definition $(ECS_TASK_FAMILY):1 --desired-count 1 --launch-type FARGATE \
	  --network-configuration "awsvpcConfiguration={subnets=[$(SUBNET_1),$(SUBNET_2)],securityGroups=[$(ECS_SG)],assignPublicIp=ENABLED}" \
	  --load-balancers "targetGroupArn=$(TG_ARN),containerName=backend,containerPort=8000" --region $(AWS_REGION)

##@ Status

.PHONY: status
status: ## Show all resource IDs and endpoints
	@echo "=== Meetings App Infrastructure ==="
	@echo "Region:          $(AWS_REGION)"
	@echo "--- Cognito Auth ---"
	@echo "Auth Stack:      $(AUTH_STACK)"
	@echo "UserPool ID:     eu-north-1_2JHnz3607"
	@echo "Client ID:       520q7rcdd0c5hf0ahk2adb8bm3"
	@echo "Cognito Domain:  anton-meetings-2026.auth.eu-north-1.amazoncognito.com"
	@echo "--- Frontend ---"
	@echo "S3 Bucket:       $(S3_BUCKET)"
	@echo "CloudFront ID:   $(CF_DISTRIBUTION_ID)"
	@echo "CloudFront URL:  https://d1y19dbl226ufk.cloudfront.net"
	@echo "--- Backend ---"
	@echo "ECR URI:         $(ECR_URI)"
	@echo "ECS Cluster:     $(ECS_CLUSTER)"
	@echo "ECS Service:     $(ECS_SERVICE)"
	@echo "ALB DNS:         meetings-alb-1279017703.eu-north-1.elb.amazonaws.com"
	@echo "--- Security & CI/CD ---"
	@echo "OIDC Role ARN:   arn:aws:iam::334177992228:role/github-actions-deploy-role"
	@echo "ALB SG:          $(ALB_SG)"
	@echo "ECS SG:          $(ECS_SG)"
	@echo "VPC:             $(VPC_ID)"

##@ Help

.PHONY: help
help: ## Show this help
	@echo "Available make targets:"
	@echo "  make aws-deploy-auth     - Deploy Cognito User Pool, Google IdP, Managed Login v2"
	@echo "  make aws-deploy-frontend - Build frontend with Cognito config, sync to S3, invalidate CloudFront"
	@echo "  make deploy-frontend     - Alias for aws-deploy-frontend"
	@echo "  make deploy-backend      - Build Docker image, push to ECR, update ECS"
	@echo "  make deploy-all          - Run full deploy pipeline (auth -> frontend -> backend)"
	@echo "  make status              - Show resource IDs and endpoints"
