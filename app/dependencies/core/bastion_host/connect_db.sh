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
    KEY_PATH=./staging-bastion-host-key-pair.pem
    BASTION_HOST=3.145.210.176
    RDS_ENDPOINT=chartwise-database-instance-staging.cx44ewmqqt62.us-east-2.rds.amazonaws.com
elif [[ "$ENV" == "prod" ]]; then
    KEY_PATH=./prod-bastion-host-key-pair.pem
    BASTION_HOST=3.147.64.230
    RDS_ENDPOINT=chartwise-database-instance-prod.cx44ewmqqt62.us-east-2.rds.amazonaws.com
else
    echo "Invalid environment: $ENV. Must be 'staging' or 'prod'."
    exit 1
fi

LOCAL_PORT=5433
RDS_PORT=5432

echo "Starting SSH tunnel to $ENV RDS via Bastion Host..."
ssh -i "$KEY_PATH" -N -L ${LOCAL_PORT}:${RDS_ENDPOINT}:${RDS_PORT} ec2-user@${BASTION_HOST}
