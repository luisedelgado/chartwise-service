# Building app Docker image

## Assume role with local script
./assume_role.sh -env staging|prod

## Authenticate Staging with ECR
aws ecr get-login-password \
  --region us-east-2 \
  --profile chartwise-staging \
| docker login --username AWS --password-stdin 637423642366.dkr.ecr.us-east-2.amazonaws.com

## Authenticate Prod with ECR
aws ecr get-login-password \
  --region us-east-2 \
  --profile chartwise-prod \
| docker login --username AWS --password-stdin 637423642366.dkr.ecr.us-east-2.amazonaws.com

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
