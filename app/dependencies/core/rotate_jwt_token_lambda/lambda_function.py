import boto3
import json
import secrets
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_client = boto3.client("secretsmanager")

def lambda_handler(event, _):
    logger.info(f"Event: {json.dumps(event)}")

    token = event["ClientRequestToken"]
    step = event["Step"]
    secret_arn = event["SecretId"]

    metadata = secrets_client.describe_secret(SecretId=secret_arn)

    if token not in metadata["VersionIdsToStages"]:
        raise ValueError("Secret version not found")
    if "AWSCURRENT" in metadata["VersionIdsToStages"][token]:
        logger.info("Secret version is already AWSCURRENT. Nothing to do.")
        return
    if "AWSPENDING" not in metadata["VersionIdsToStages"][token]:
        raise ValueError("Secret version is not set as AWSPENDING for rotation")

    if step == "createSecret":
        create_secret(secret_arn, token)
    elif step == "finishSecret":
        finish_secret(secret_arn, token)
    elif step == "setSecret" or step == "testSecret":
        # Nothing to do for stateless secrets like this one.
        return
    else:
        raise ValueError(f"Unknown step: {step}")

    return {"statusCode": 200, "body": "Done"}

def create_secret(secret_arn, token):
    try:
        # Check if version already exists
        secrets_client.get_secret_value(SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING")
        logger.info("createSecret: Version already exists")
    except secrets_client.exceptions.ResourceNotFoundException:
        # Generate 64-character hex string (32 bytes)
        new_secret = secrets.token_hex(32)
        logger.info(f"createSecret: Generated new secret")

        secrets_client.put_secret_value(
            SecretId=secret_arn,
            ClientRequestToken=token,
            SecretString=new_secret,
            VersionStages=["AWSPENDING"]
        )

def finish_secret(secret_arn, token):
    metadata = secrets_client.describe_secret(SecretId=secret_arn)
    current_version = None

    for version_id, stages in metadata["VersionIdsToStages"].items():
        if "AWSCURRENT" in stages:
            current_version = version_id
            break

    if current_version == token:
        logger.info("finishSecret: Version already marked as AWSCURRENT")
        return

    secrets_client.update_secret_version_stage(
        SecretId=secret_arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=current_version
    )
    logger.info("finishSecret: Promoted new version to AWSCURRENT")
