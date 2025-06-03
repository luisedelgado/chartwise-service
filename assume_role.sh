#!/bin/bash

# Usage:source ./assume_role.sh -env staging|prod

unset ENVIRONMENT

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --env)
      ENVIRONMENT="$2"
      shift
      ;;
    *)
      echo "Unknown parameter: $1"
      exit 1
      ;;
  esac
  shift
done

if [[ -z "$ENVIRONMENT" ]]; then
  echo "Error: -env flag is required (staging or prod)"
  exit 1
fi

# Define role ARN based on environment
if [[ "$ENVIRONMENT" == "staging" ]]; then
  ROLE_ARN="arn:aws:iam::637423642366:role/ChartWiseUserStaging"
  SESSION_NAME="chartwise-session-staging"
elif [[ "$ENVIRONMENT" == "prod" ]]; then
  ROLE_ARN="arn:aws:iam::637423642366:role/ChartWiseUserProd"
  SESSION_NAME="chartwise-session-prod"
else
  echo "Invalid environment: $ENVIRONMENT. Use 'staging' or 'prod'."
  exit 1
fi

CREDS_JSON=$(aws sts assume-role --role-arn "$ROLE_ARN" --role-session-name "$SESSION_NAME" --output json)

if [[ $? -ne 0 ]]; then
  echo "Failed to assume role for environment '$ENVIRONMENT'"
  exit 1
fi

export AWS_ACCESS_KEY_ID=$(echo "$CREDS_JSON" | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS_JSON" | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "$CREDS_JSON" | jq -r '.Credentials.SessionToken')

echo "✅ Assumed role $ROLE_ARN and updated environment variables."
