FROM public.ecr.aws/lambda/python:3.11-arm64

RUN yum install -y gcc postgresql-devel python3-devel zip

WORKDIR /app

# Install dependencies locally to /app
COPY requirements.txt .
RUN pip install -r requirements.txt -t .

# Add your handler
COPY lambda_function.py .

CMD ["zip", "-r9", "lambda_payload.zip", "."]
