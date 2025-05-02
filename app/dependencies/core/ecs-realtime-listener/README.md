# Building listener docker image

## Commands for Staging
```
export TAG=staging-v1-$(date +%Y%m%d%H%M) && docker buildx build \
  --platform linux/amd64 \
  -t 637423642366.dkr.ecr.us-east-2.amazonaws.com/staging-chartwise-realtime-listener:$TAG \
  --push \
  .
```

## Commands for Prod
```
export TAG=prod-v1-$(date +%Y%m%d%H%M) && docker buildx build \
  --platform linux/amd64 \
  -t 637423642366.dkr.ecr.us-east-2.amazonaws.com/prod-chartwise-realtime-listener:$TAG \
  --push \
  .
```
