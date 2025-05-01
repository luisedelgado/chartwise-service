#!/bin/bash

# Path to your private key
KEY_PATH=./staging-bastion-host-key-pair.pem

# Bastion public IP
BASTION_HOST=3.134.187.106

# RDS private endpoint
RDS_ENDPOINT=chartwise-database-instance-staging.cx44ewmqqt62.us-east-2.rds.amazonaws.com

# Local port to forward
LOCAL_PORT=5433

# Target RDS port
RDS_PORT=5432

echo "Starting SSH tunnel to staging RDS via Bastion Host..."
ssh -i "$KEY_PATH" -N -L ${LOCAL_PORT}:${RDS_ENDPOINT}:${RDS_PORT} ec2-user@${BASTION_HOST}
