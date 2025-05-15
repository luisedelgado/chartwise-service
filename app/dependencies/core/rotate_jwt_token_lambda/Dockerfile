FROM public.ecr.aws/lambda/python:3.11

# Install zip
RUN yum install -y zip

# Set working directory
WORKDIR /var/task

COPY lambda_function.py .

# Create deployment package
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find . -type f -name "*.pyc" -delete 2>/dev/null || true && \
    zip -r9 /lambda.zip .

# Set default command
CMD ["echo", "Lambda package created at /lambda.zip"]
