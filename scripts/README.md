Steps for updating a Fly.io scheduled machine (Pending Jobs daily script)

1. Test locally by running the script in a docker container (`docker-compose up --build --remove-orphans`), and attach a debugger.

1. `> docker build --platform linux/amd64 -f scripts/pending_audio_jobs_script.Dockerfile -t registry.fly.io/process-pending-jobs:latest .`

2. `> docker tag process-pending-jobs registry.fly.io/process-pending-jobs:latest`

3. `> docker push registry.fly.io/process-pending-jobs:latest`

4. `> fly machines run registry.fly.io/process-pending-jobs:latest --schedule daily -a process-pending-jobs --vm-cpu-kind 'shared' --vm-cpus 2 --vm-memory 1024`
