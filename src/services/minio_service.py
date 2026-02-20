from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile
from src.config.settings import Settings


class MinioService:
    def __init__(self):
        settings = Settings()
        self.client = Minio(
            endpoint=f"{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}",
            access_key=settings.S3_STORAGE_ACCESS_KEY,
            secret_key=settings.S3_STORAGE_SECRET_KEY,
            secure=False
        )
        self.bucket_name = settings.S3_BUCKET_NAME
        self.ensure_bucket_exists()

    def ensure_bucket_exists(self):
        found = self.client.bucket_exists(self.bucket_name)
        if not found:
            self.client.make_bucket(self.bucket_name)

    async def upload_file(self, file: UploadFile, object_name: str) -> str:
        settings = Settings()
        try:
            file_content = await file.read()
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=bytes(file_content),
                length=len(file_content),
                content_type=file.content_type,
            )
            url = f"http://{settings.S3_STORAGE_HOST}:{settings.S3_STORAGE_PORT}/{self.bucket_name}/{object_name}"
            return url
        except S3Error as err:
            raise RuntimeError(f"MinIO error: {err}")