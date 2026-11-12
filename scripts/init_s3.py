import os
import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

def create_bucket():
    s3_endpoint = os.getenv("AWS_S3_ENDPOINT_URL", "http://localhost:9000")
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME", "3dprint-models")

    print(f"Connecting to S3 at {s3_endpoint}...")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=s3_endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='us-east-1'
    )

    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Бакет '{bucket_name}' уже существует.")
        
    except EndpointConnectionError:
        print("\n❌ERROR: Failed to connect to S3 storage.")
        print("Ensure that Docker Desktop is running,")
        print("and execute the following in your terminal:")
        print("   docker compose up -d")
        exit(1)
        
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            print(f"Bucket '{bucket_name}' not found. Creating...")
            try:
                s3_client.create_bucket(Bucket=bucket_name)
                print(f"Bucket '{bucket_name}' has been created")
            except Exception as create_error:
                print(f"Error creating bucket: {create_error}")
        else:
            print(f"Error while checking the bucket: {e}")

if __name__ == "__main__":
    create_bucket()