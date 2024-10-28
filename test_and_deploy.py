import argparse, subprocess, os, pty

from pathlib import Path

# Command for executing: python test_and_deploy.py -env <environment>

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
    venv_python_dir = Path("/Users/luisdelgado/Documents/APIs/RAGService/.venv311/bin")
    if not venv_python_dir.is_dir():
        print(f"The following virtual env directory was not found: {venv_python_dir}")
        return False

    venv_python = "/Users/luisdelgado/Documents/APIs/RAGService/.venv311/bin/python"
    tests_result = subprocess.run([venv_python, "-m", "pytest", "-p", "no:warnings"], capture_output=True, text=True)
    print(tests_result.stdout)
    if tests_result.returncode != 0:
        return False

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a command and perform an action if it succeeds.")
    parser.add_argument("-env", nargs=1, help="The environment to deploy if tests succeed")
    env = parser.parse_args().env[0]

    if env == "staging":
        toml_file_name = "fly.staging.toml"
        app_name = "chartwise-staging-service"
    elif env == "prod":
        toml_file_name = "fly.prod.toml"
        app_name = "chartwise-service-prod"
    else:
        print(f"How did I get here? No env to deploy based on: {env}")
        exit()

    if env != "staging" and env != "prod":
        print("Invalid environment to deploy.")
        exit()

    print("Running tests...\n")
    tests_passed = run_tests()
    if not tests_passed:
        print("Some tests failed.")
        exit()

    print("All tests passed!\n")

    print("\nDeploying FastAPI app...")
    deploy_process(commands=["fly",
                            "deploy",
                            "-c",
                            toml_file_name,
                            "-a",
                            app_name])

    print("\nDone")
