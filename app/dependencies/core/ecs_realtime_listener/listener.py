print("🔥 Listener container booting up")

import boto3
import os
import json
import psycopg2
import select
import redis

SECRET_STRING_KEY = "SecretString"

# Initialize at module level
redis_client = redis.StrictRedis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ["REDIS_PORT"]),
    password=os.environ["REDIS_AUTH_TOKEN"],
    db=0,
    decode_responses=True
)

def get_secret(secret_name: str) -> dict:
    try:
        client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_SERVICES_REGION"),
        )
        response = client.get_secret_value(SecretId=secret_name)

        assert SECRET_STRING_KEY in response, f"Failed to find {SECRET_STRING_KEY} in secretsmanager response"

        secret_string = response[SECRET_STRING_KEY]
        return json.loads(secret_string)
    except Exception as e:
        error_msg = f"Failed to get secret: {e}"
        print(error_msg)
        raise RuntimeError(error_msg) from e

def get_db_connection():
    secret = get_secret(os.environ.get("AWS_SECRET_MANAGER_PROCESSING_STATUS_UPDATER_ROLE"))
    print("[get_db_connection] Retrieved secret successfully")
    return psycopg2.connect(
        host=secret.get("host"),
        dbname=secret.get("dbname"),
        user=secret.get("username"),
        password=secret.get("password"),
        port=secret.get("port"),
        sslmode="require",
    )

def publish_to_external_service(payload):
    try:
        therapist_id = payload["therapist_id"]
        redis_key = f"therapist:{therapist_id}:connections"

        # Redis returns a set of connection IDs (assumes you use Redis sets)
        connection_ids = redis_client.smembers(redis_key)

        if not connection_ids:
            print(f"No active WebSocket connections in Redis for therapist_id: {therapist_id}")
            return

        gatewayapi = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=f"https://{os.environ.get('WEBSOCKET_DOMAIN')}/{os.environ.get('WEBSOCKET_STAGE')}"
        )

        for conn_id in connection_ids:
            try:
                gatewayapi.post_to_connection(
                    ConnectionId=conn_id,
                    Data=json.dumps(payload).encode("utf-8")
                )
                print(f"✅ Sent update to connection {conn_id}")
            except gatewayapi.exceptions.GoneException:
                print(f"⚠️ Connection {conn_id} is stale — let $disconnect clean it up")
            except Exception as e:
                print(f"❌ Failed to send to {conn_id}: {e}")

    except Exception as e:
        print(f"[publish_to_external_service] Unexpected error: {e}")

def main():
    print("[Listener] Starting realtime listener.")
    conn = get_db_connection()
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("LISTEN session_report_update_channel;")
    print("[Listener] Listening on 'session_report_update_channel'...")

    while True:
        if select.select([conn], [], [], 5) == ([], [], []):
            continue
        conn.poll()
        while conn.notifies:
            notify = conn.notifies.pop(0)
            try:
                data = json.loads(notify.payload)
                event_type = data.get("event_type")
                print(f"[Listener] Received event: {event_type} for session_id: {data.get('id')}")
                publish_to_external_service(data)
            except Exception as e:
                print(f"[Listener Error] {e}")

if __name__ == "__main__":
    main()
