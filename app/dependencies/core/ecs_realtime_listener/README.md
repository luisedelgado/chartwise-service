## Assume role with local script
assume_role --env staging|prod

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

## Command for pushing to ECR
```
export TAG=realtime-listener-$(date +%Y%m%d%H%M) && docker buildx build \
  --no-cache \
  --platform linux/amd64 \
  -t 637423642366.dkr.ecr.us-east-2.amazonaws.com/chartwise-realtime-listener:$TAG \
  --push \
  .
```
