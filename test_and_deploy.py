import argparse, subprocess, os, pty

from pathlib import Path

# Command for executing: python test_and_deploy.py -env <environment>

def run_tests_and_deploy_if_success(env_to_deploy):
    venv_python_dir = Path("/Users/luisdelgado/Documents/APIs/RAGService/.venv311/bin")
    if not venv_python_dir.is_dir():
        print(f"The following virtual env directory was not found: {venv_python_dir}")
        return

    venv_python = "/Users/luisdelgado/Documents/APIs/RAGService/.venv311/bin/python"
    tests_result = subprocess.run([venv_python, "-m", "pytest", "-p", "no:warnings"], capture_output=True, text=True)
    print(tests_result.stdout)
    if tests_result.returncode != 0:
        print("Some tests failed.")
        return

    print("All tests passed!")

    if env_to_deploy == "staging":
        toml_file_name = "fly.staging.toml"
        app_name = "chartwise-service-staging"
    elif env_to_deploy == "prod":
        toml_file_name = "fly.prod.toml"
        app_name = "chartwise-service-prod"
    else:
        print(f"How did I get here? No env to deploy based on: {env}")

    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(["fly",
                                "deploy",
                                "-c",
                                toml_file_name,
                                "-a",
                                app_name],
                            stdin=slave_fd,
                            stdout=slave_fd,
                            stderr=slave_fd,
                            universal_newlines=True)
    os.close(slave_fd)

    try:
        while True:
            output = os.read(master_fd, 1024).decode('utf-8')
            if output == "":
                if process.poll() is not None:
                    break
            if output:
                print(output, end='', flush=True)
    except KeyboardInterrupt:
        process.terminate()

    os.close(master_fd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a command and perform an action if it succeeds.")
    parser.add_argument("-env", nargs=1, help="The environment to deploy if tests succeed")

    env = parser.parse_args().env[0]
    if env != "staging" and env != "prod":
        print("Invalid environment to deploy.")
    else:
        run_tests_and_deploy_if_success(env)
