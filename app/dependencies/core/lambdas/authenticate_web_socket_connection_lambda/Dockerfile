FROM public.ecr.aws/lambda/python:3.11

# Install zip
RUN yum install -y zip

# Set working directory
WORKDIR /var/task

# Copy requirements and function code
COPY requirements.txt .
COPY lambda_function.py .

# Install dependencies with special handling for cryptography
RUN pip install --upgrade pip && \
    python -m pip install --platform=manylinux2014_x86_64 --only-binary=:all: --target . cryptography && \
    pip install -r requirements.txt --target .

# Create deployment package
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find . -type f -name "*.pyc" -delete 2>/dev/null || true
RUN zip -r9 /lambda.zip .

# Set default command
CMD ["echo", "Lambda package created at /lambda.zip"]
