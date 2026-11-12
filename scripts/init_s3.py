import os
import boto3
from botocore.exceptions import ClientError

def create_bucket():
    # Берем настройки из переменных окружения (или ставим дефолтные для локалки)
    s3_endpoint = os.getenv("AWS_S3_ENDPOINT_URL", "http://localhost:9000")
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME", "3dprint-models")

    print(f"Подключение к S3 по адресу {s3_endpoint}...")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=s3_endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='us-east-1' # Для MinIO/SILO можно указать любой
    )

    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Бакет '{bucket_name}' уже существует.")
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            print(f"Бакет '{bucket_name}' не найден. Создаем...")
            try:
                s3_client.create_bucket(Bucket=bucket_name)
                print(f"Бакет '{bucket_name}' успешно создан!")
            except Exception as create_error:
                print(f"Ошибка при создании бакета: {create_error}")
        else:
            print(f"Ошибка при проверке бакета: {e}")

if __name__ == "__main__":
    # Проверяем, установлена ли библиотека boto3
    try:
        import boto3
    except ImportError:
        print("Ошибка: Библиотека boto3 не установлена.")
        print("Установите её командой: pip install boto3")
        exit(1)
        
    create_bucket()