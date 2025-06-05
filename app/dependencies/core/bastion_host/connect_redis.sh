#!/bin/bash

# Ensure --env flag is provided
if [[ "$1" != "--env" || -z "$2" ]]; then
    echo "❌ Error: Missing required --env argument."
    echo "Usage: $0 --env staging|prod"
    exit 1
fi

# Extract environment
ENV="$2"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift
            ;;
        *)
            echo "Unknown parameter passed: $1"
            echo "Usage: $0 [--env staging|prod]"
            exit 1
            ;;
    esac
    shift
done

# Set variables based on environment
if [[ "$ENV" == "staging" ]]; then
    KEY_PATH=./staging-redis-store.pem
    BASTION_HOST=18.224.169.79
    REDIS_ENDPOINT=master.chartwisewebsocketcachestaging.uv8qhp.use2.cache.amazonaws.com
elif [[ "$ENV" == "prod" ]]; then
    KEY_PATH=./prod-redis-store.pem
    BASTION_HOST=0
    REDIS_ENDPOINT=0
else
    echo "Invalid environment: $ENV. Must be 'staging' or 'prod'."
    exit 1
fi

LOCAL_PORT=6379
REDIS_PORT=6379

echo "Starting SSH tunnel to $ENV Redis via Bastion Host..."
ssh -i "$KEY_PATH" -N -L ${LOCAL_PORT}:${REDIS_ENDPOINT}:${REDIS_PORT} ec2-user@${BASTION_HOST}
