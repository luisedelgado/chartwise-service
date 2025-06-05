# Commands to run for generating .zip file

docker build --no-cache -t lambda-builder .

docker create --name lambda-extractor lambda-builder

docker cp lambda-extractor:/lambda.zip ./lambda-new.zip

docker rm lambda-extractor

# Delete zip file after uploading to Lambda

rm lambda-new.zip 