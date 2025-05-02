print("🔥 Listener container booting up")

import boto3
import os
import json
import psycopg2
import select

SECRET_STRING_KEY = "SecretString"

def get_secret(secret_name: str) -> dict:
    try:
        client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_SERVICES_REGION"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
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
    secret = get_secret(os.environ.get("AWS_SECRET_MANAGER_CHARTWISE_USER_ROLE"))
    print("[get_db_connection] Retrieved secret successfully")
    return psycopg2.connect(
        host=secret.get("host"),
        dbname=secret.get("dbname"),
        user=secret.get("username"),
        password=secret.get("password"),
        port=secret.get("port"),
        sslmode="require",
    )

def fetch_row(conn, id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, processing_status, therapist_id FROM encrypted_session_reports WHERE id = %s",
            (id,)
        )
        row = cur.fetchone()
        return {
            "id": row[0],
            "new_value": row[1],
            "user_id": row[2],
        }

def publish_to_external_service(payload):
    print("Publishing payload:", payload)
    # For now, just log it or forward to WebSocket/SNS/etc.
    # requests.post(YOUR_ENDPOINT, json=payload)

def main():
    print("[Listener] Starting realtime listener.")
    conn = get_db_connection()
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("LISTEN processing_status_update_channel;")
    print("[Listener] Listening on 'processing_status_update_channel'...")

    while True:
        if select.select([conn], [], [], 5) == ([], [], []):
            continue
        conn.poll()
        while conn.notifies:
            notify = conn.notifies.pop(0)
            try:
                data = json.loads(notify.payload)
                row = fetch_row(conn, data["id"])
                publish_to_external_service(row)
            except Exception as e:
                print(f"[Listener Error] {e}")

if __name__ == "__main__":
    main()
