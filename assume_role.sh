#!/bin/bash

# Usage: ./assume_role.sh -env staging|prod

while [[ "$#" -gt 0 ]]; do
  case $1 in
    -env)
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
elif [[ "$ENVIRONMENT" == "prod" ]]; then
  ROLE_ARN="arn:aws:iam::637423642366:role/ChartWiseUserProd"
else
  echo "Invalid environment: $ENVIRONMENT. Use 'staging' or 'prod'."
  exit 1
fi

SESSION_NAME="chartwise-dev-session"
CREDS_JSON=$(aws sts assume-role --role-arn "$ROLE_ARN" --role-session-name "$SESSION_NAME" --output json)

if [[ $? -ne 0 ]]; then
  echo "Failed to assume role for environment '$ENVIRONMENT'"
  exit 1
fi

AWS_ACCESS_KEY_ID=$(echo "$CREDS_JSON" | jq -r '.Credentials.AccessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo "$CREDS_JSON" | jq -r '.Credentials.SecretAccessKey')
AWS_SESSION_TOKEN=$(echo "$CREDS_JSON" | jq -r '.Credentials.SessionToken')

echo "export AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"
echo "export AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"
echo "export AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN"
