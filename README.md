# Building app Docker image

## Authenticate with ECR
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 637423642366.dkr.ecr.us-east-2.amazonaws.com

## Commands for Staging
```
export TAG=staging-v1-$(date +%Y%m%d%H%M) && docker buildx build \
  --platform linux/amd64 \
  -t 637423642366.dkr.ecr.us-east-2.amazonaws.com/staging-chartwise-app:$TAG \
  --push \
  .
```

## Commands for Prod
```
export TAG=prod-v1-$(date +%Y%m%d%H%M) && docker buildx build \
  --platform linux/amd64 \
  -t 637423642366.dkr.ecr.us-east-2.amazonaws.com/prod-chartwise-app:$TAG \
  --push \
  .
```
