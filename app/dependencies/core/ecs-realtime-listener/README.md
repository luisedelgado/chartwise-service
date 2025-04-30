# Building listener docker image

## Commands for Staging
```
docker build -t chartwise-realtime-listener .

docker tag chartwise-realtime-listener:latest 637423642366.dkr.ecr.us-east-2.amazonaws.com/staging-chartwise-realtime-listener:latest

docker push 637423642366.dkr.ecr.us-east-2.amazonaws.com/staging-chartwise-realtime-listener:latest
```

## Commands for Prod
```
docker build -t chartwise-realtime-listener .

docker tag chartwise-realtime-listener:latest 637423642366.dkr.ecr.us-east-2.amazonaws.com/prod-chartwise-realtime-listener:latest

docker push 637423642366.dkr.ecr.us-east-2.amazonaws.com/prod-chartwise-realtime-listener:latest
```