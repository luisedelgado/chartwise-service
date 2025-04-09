import argparse, json, subprocess, os, pty

from app.internal.schemas import STAGING_ENVIRONMENT, PROD_ENVIRONMENT
from pathlib import Path

ALWAYS_ON_REGIONS = {"mia", "dfw"}

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
    venv_python_dir = Path("/Users/luisdelgado/Documents/ChartWiseServiceApp/chartwise-service/.venv/bin")
    if not venv_python_dir.is_dir():
        print(f"The following virtual env directory was not found: {venv_python_dir}")
        return False

    venv_python = "/Users/luisdelgado/Documents/ChartWiseServiceApp/chartwise-service/.venv/bin/python"
    tests_result = subprocess.run([venv_python, "-m", "pytest", "-p", "no:warnings"], capture_output=True, text=True)
    print(tests_result.stdout)
    if tests_result.returncode != 0:
        return False

    return True

def update_autostop_for_always_on_regions(app_name: str):
    print("\nNow checking machine autostop configs in always-on regions...\n")

    # Fetch all machines as JSON
    result = subprocess.run(
        ["fly", "machines", "list", "-a", app_name, "--json"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print("❌ Failed to fetch machines list.")
        print(result.stderr)
        return

    machines = json.loads(result.stdout)

    for machine in machines:
        region = machine.get("region")
        machine_id = machine.get("id")
        config_services = machine.get("config", {}).get("services", [])

        if region in ALWAYS_ON_REGIONS:
            autostop = config_services[0].get("autostop") if config_services else None
            if autostop == False or autostop == "off":
                continue

            print(f"🔧 Updating autostop for machine {machine_id} in {region}...\n")
            subprocess.run([
                "fly", "machine", "update", machine_id,
                "--autostop=off",
                "--autostart=true",
                "-a", app_name
            ])

def deploy_fastapi_app(env):
    if env == STAGING_ENVIRONMENT:
        toml_file_name = "fly.app.staging.toml"
        app_name = "chartwise-staging-service"
    elif env == PROD_ENVIRONMENT:
        toml_file_name = "fly.app.prod.toml"
        app_name = "chartwise-service-prod"
    else:
        print(f"How did I get here? No env to deploy based on: {env}")
        exit()

    if env != STAGING_ENVIRONMENT and env != PROD_ENVIRONMENT:
        print("Invalid environment to deploy.")
        exit()

    print("Running tests...\n")
    tests_passed = run_tests()
    if not tests_passed:
        print("Some tests failed.")
        exit()

    print("All tests passed!\n")

    print(f"✅ Deploying FastAPI app in '{env}' environment")
    deploy_process(commands=["fly",
                            "deploy",
                            "-c",
                            toml_file_name,
                            "-a",
                            app_name,
                            "--dockerfile",
                            "Dockerfile.app"])

    if env == PROD_ENVIRONMENT:
        update_autostop_for_always_on_regions(app_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy the FastAPI app.")
    parser.add_argument(
        "-env", "--environment", required=True, choices={STAGING_ENVIRONMENT, PROD_ENVIRONMENT},
        help="Deployment environment for the webapp: 'staging' or 'prod'"
    )

    args = parser.parse_args()
    env = args.environment

    deploy_fastapi_app(env)
    print("\nDone")
