import boto3
import json
import os
import psycopg2
import select
import requests

CHARTWISE_USER_ROLE = "chartwise_user"
SECRET_BINARY_KEY = "SecretBinary"

def get_secret(secret_name: str) -> dict:
    try:
        client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_SERVICES_REGION"))
        response = client.get_secret_value(SecretId=secret_name)
        assert "SecretString" in response, f"Failed to find {SECRET_BINARY_KEY} in secretsmanager response"
        secret_string = response["SecretString"]
        return json.loads(secret_string)
    except Exception as e:
        error_msg = f"Failed to get secret: {e}"
        print(error_msg)
        raise RuntimeError(error_msg) from e

def send_to_appsync(payload: dict):
    endpoint = os.environ.get("APPSYNC_GRAPHQL_ENDPOINT")
    api_key = os.environ.get("APPSYNC_API_KEY")

    mutation = """
    mutation PublishColumnUpdate($input: ColumnUpdateInput!) {
      publishColumnUpdate(input: $input) {
        id
        new_value
      }
    }
    """
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    body = {
        "query": mutation,
        "variables": {"input": payload}
    }
    try:
        response = requests.post(endpoint, headers=headers, json=body)
        print(f"[AppSync Response] {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[AppSync Error] {e}")

def handle_change(payload):
    print(f"[DB Notification Received]: {payload}")
    try:
        data = json.loads(payload)
        send_to_appsync(data)
    except Exception as e:
        print(f"[Payload Processing Error]: {e}")

def lambda_handler(event, context):
    try:
        print("[Lambda] Handler started.")

        # Load secret and database connection
        secret = get_secret(os.environ.get("AWS_SECRET_MANAGER_CHARTWISE_USER_ROLE"))

        print("[Lambda] Retrieved secret successfully.")
        conn = psycopg2.connect(
            host=secret.get("host"),
            dbname=secret.get("dbname"),
            user=secret.get("username"),
            password=secret.get("password"),
            port=secret.get("port"),
            sslmode="require",
        )

        print("[Lambda] Established a connection successfully.")

        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("LISTEN column_update_channel;")
        print("[Lambda] Listening on channel: column_update_channel")

        # ✅ Listen indefinitely (until Lambda timeout ends ~15 min)
        while True:
            if select.select([conn], [], [], 5) == ([], [], []):
                continue
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                handle_change(notify.payload)

    except Exception as e:
        print(f"[Fatal Error]: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error: {str(e)}")
        }
