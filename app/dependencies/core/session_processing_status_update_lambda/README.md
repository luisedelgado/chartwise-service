# All environment variables for this lambda are stored directly in AWS Lambda

# Commands to run after updating lambda_function.py:
docker run --name lambda-zip-runner --entrypoint "" lambda-zip-packager zip -r9 lambda_payload.zip .
docker cp lambda-zip-runner:/app/lambda_payload.zip .
docker rm lambda-zip-runner
