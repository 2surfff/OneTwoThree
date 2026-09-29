# ============================================================================
# Meetings App — ECS Fargate deployment contract (Makefile)
# Usage:  make deploy-frontend   (build + S3 sync + CloudFront invalidation)
#         make deploy-backend    (ECR login, Docker build, push, ECS redeploy)
#         make deploy-infra      (one-time: create all AWS resources)
# ============================================================================
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Configuration (override via environment or command line)
# ---------------------------------------------------------------------------
AWS_REGION         ?= eu-north-1
AWS_ACCOUNT_ID     ?= 334177992228
PROJECT            ?= meetings

# Frontend
S3_BUCKET          ?= $(PROJECT)-frontend-$(AWS_ACCOUNT_ID)
CF_DISTRIBUTION_ID ?= ESXCTSSJ27R0H

# Backend
ECR_REPO           ?= $(PROJECT)-backend
ECR_URI            ?= $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO)
ECS_CLUSTER        ?= $(PROJECT)-cluster
ECS_SERVICE        ?= $(PROJECT)-backend-svc
ECS_TASK_FAMILY    ?= $(PROJECT)-backend-task

# Network (default VPC)
VPC_ID             ?= vpc-06a44a341230eac1f
SUBNET_1           ?= subnet-04f8a8ab3ddd48bca
SUBNET_2           ?= subnet-051036efda8009e98
ALB_SG             ?= sg-06257b3ed60d576f7
ECS_SG             ?= sg-03ae0158551fe30b0
TG_ARN             ?= arn:aws:elasticloadbalancing:eu-north-1:334177992228:targetgroup/meetings-backend-tg/71809a34245ffbb2

# Commit SHA for image tagging
TAG                ?= $(shell git rev-parse --short HEAD)

##@ Deployment

.PHONY: deploy-frontend
deploy-frontend: ## Build frontend, sync to S3, invalidate CloudFront
	@echo "==> Building frontend..."
	cd front && npm run build
	@echo "==> Syncing to S3 bucket $(S3_BUCKET)..."
	aws s3 sync front/dist "s3://$(S3_BUCKET)" --delete --region $(AWS_REGION)
	@echo "==> Creating CloudFront invalidation..."
	aws cloudfront create-invalidation \
	  --distribution-id $(CF_DISTRIBUTION_ID) --paths "/*" \
	  --query "Invalidation.Status" --output text
	@echo "==> Frontend deployed!"

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
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} \
	  /^[a-zA-Z_.-]+:.*?##/ { printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
