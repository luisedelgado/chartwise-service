import argparse, json, subprocess, os, pty

from app.internal.schemas import STAGING_ENVIRONMENT, PROD_ENVIRONMENT
from datetime import datetime, timezone
from pathlib import Path

def deploy_process(commands: list[str]):
    master_fd, slave_fd = pty.openpty()

    process = subprocess.Popen(commands,
                               stdin=slave_fd,
                               stdout=slave_fd,
                               stderr=slave_fd,
                               universal_newlines=True)
    os.close(slave_fd)

    try:
        while True:
            output = os.read(master_fd, 1024).decode('utf-8')
            if output != "":
                print(output, end='', flush=True)
                continue
            status = process.poll()
            if status is not None:
                break
    except KeyboardInterrupt:
        process.terminate()

    while (True):
        status = process.poll()
        if status is None:
            continue
        else:
            process.terminate()
            break

    os.close(master_fd)

def run_tests() -> bool:
    current_directory = os.getcwd()
    full_path = os.path.join(current_directory, ".venv", "bin")
    venv_bin_dir = Path(full_path)
    if not venv_bin_dir.is_dir():
        print(f"The following virtual env directory was not found: {venv_bin_dir}")
        return False

    venv_python = os.path.join(full_path, "python")
    tests_result = subprocess.run([venv_python, "-m", "pytest", "-p", "no:warnings"], capture_output=True, text=True)
    print(tests_result.stdout)
    if tests_result.returncode != 0:
        return False

    return True

def deploy_fastapi_app(env):
    print("Running tests...\n")
    tests_passed = run_tests()
    if not tests_passed:
        print("Some tests failed.")
        exit()

    print("All tests passed! ✅\n")
    try:
        assume_role(env)
        print("Logging into ECR 🔐")
        profile_name = "chartwise-staging" if env == STAGING_ENVIRONMENT else "chartwise-prod"
        deploy_process(
            commands=[
                "bash",
                "-c",
                (
                    f"aws ecr get-login-password --region us-east-2 --profile {profile_name} | "
                    f"docker login --username AWS --password-stdin {os.environ.get('AWS_ACCOUNT_ID')}.dkr.ecr.us-east-2.amazonaws.com"
                )
            ]
        )

        ecr_repo_name = "chartwise-main-app"
        image_tag = f"main-app-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        full_image_uri = f"{os.environ.get('AWS_ACCOUNT_ID')}.dkr.ecr.us-east-2.amazonaws.com/{ecr_repo_name}:{image_tag}"
        
        print("Pushing new docker image to ECR 📦")
        deploy_process(
            commands=[
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                full_image_uri,
                "--push",
                "."
            ]
        )
        print("\nPush succeeded 🎈\n")

        task_definition_name = (
            "staging-chartwise-main-app-task" if env == STAGING_ENVIRONMENT
            else "prod-chartwise-main-app-task"
        )

        describe_current_task_result = subprocess.run(
            [
                "aws",
                "ecs",
                "describe-task-definition",
                "--task-definition",
                task_definition_name,
                "--profile",
                profile_name
            ],
            capture_output=True,
            text=True,
            check=True
        )
        assert describe_current_task_result == 0, "Failed to describe task definition"
        task_def = json.loads(describe_current_task_result.stdout)["taskDefinition"]

        for container in task_def["containerDefinitions"]:
            container["image"] = full_image_uri

        keys_to_keep = [
            "family",
            "taskRoleArn",
            "executionRoleArn",
            "networkMode",
            "containerDefinitions",
            "volumes",
            "requiresCompatibilities",
            "cpu",
            "memory",
            "enableFaultInjection",
            "runtimePlatform",
        ]
        task_def_input = {k: task_def[k] for k in keys_to_keep if k in task_def}

        # Write temp JSON file
        with open("new_task_def.json", "w") as f:
            json.dump(task_def_input, f)

        # Register new revision
        print("Registering new task definition pointing to the new image's URI 🐳")
        register_result = subprocess.run(
            [
                "aws",
                "ecs",
                "register-task-definition",
                "--cli-input-json",
                f"file://new_task_def.json"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        assert register_result == 0, "Failed to register new task definition"

        describe_new_task_result = subprocess.run(
            [
                "aws",
                "ecs",
                "describe-task-definition",
                "--task-definition",
                task_definition_name
            ],
            capture_output=True,
            text=True,
            check=True
        )
        assert describe_new_task_result == 0, "Failed to describe new task definition"
        revision = json.loads(describe_new_task_result.stdout)["taskDefinition"]["revision"]

        cluster_name = "staging-chartwise-app-cluster" if env == STAGING_ENVIRONMENT else "prod-chartwise-app-cluster"
        service_name = "staging-chartwise-main-app-task-service" if env == STAGING_ENVIRONMENT else "prod-chartwise-main-app-task-service"

        print(f"\nUpdating ECS service '{service_name}' in cluster '{cluster_name}' to use new image 🔄")
        update_service_result = subprocess.run(
            [
                "aws",
                "ecs",
                "update-service",
                "--cluster",
                cluster_name,
                "--service",
                service_name,
                "--task-definition",
                f"{task_definition_name}:{revision}",
                "--force-new-deployment"
            ],
            check=True,
            capture_output=True,
            text=True
        )
        assert update_service_result == 0, "Failed to update ECS service"

        os.remove("new_task_def.json")
        print("AWS deployment complete 🎊.")
    except Exception as e:
        print(f"Something went wrong ⚠️ – {str(e)}")

def assume_role(env):
    try:
        role_arn = {
            "staging": f"arn:aws:iam::{os.environ.get('AWS_ACCOUNT_ID')}:role/ChartWiseUserStaging",
            "prod": f"arn:aws:iam::{os.environ.get('AWS_ACCOUNT_ID')}:role/ChartWiseUserProd"
        }.get(env)

        print(f"Assuming role {role_arn} 👤")

        if not role_arn:
            raise ValueError("Invalid env")

        result = subprocess.run(
            [
                "aws",
                "sts",
                "assume-role",
                "--role-arn",
                role_arn,
                "--role-session-name",
                f"chartwise-session-{env}"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        assert result == 0, "Failed to assume role"

        creds = json.loads(result.stdout)["Credentials"]

        os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
        os.environ["AWS_SESSION_TOKEN"] = creds["SessionToken"]

        print(f"Assumed role successfully 🎯")
    except Exception as e:
        print(f"Something went wrong ⚠️ – {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy the FastAPI app.")
    parser.add_argument(
        "-e", "--env", required=True, choices={STAGING_ENVIRONMENT, PROD_ENVIRONMENT},
        help="Deployment environment for the webapp: 'staging' or 'prod'"
    )

    args = parser.parse_args()
    env = args.env or args.e
    deploy_fastapi_app(env)
    print("\nDone")
