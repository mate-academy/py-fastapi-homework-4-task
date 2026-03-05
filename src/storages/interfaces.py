from abc import ABC, abstractmethod
from typing import Union


class S3StorageInterface(ABC):

    @abstractmethod
    async def upload_file(
        self,
        file_name: str,
        file_data: Union[bytes, bytearray],
        content_type: str = "application/octet-stream"
    ) -> None:
        """
        Uploads a file to the storage.

        :param file_name: The name of the file to be stored.
        :param file_data: The file data in bytes.
        :param content_type: The content type of the file. Defaults to "application/octet-stream".
        :return: URL of the uploaded file.
        """
        pass

    @abstractmethod
    async def get_file_url(self, file_name: str) -> str:
        """
        Generate a public URL for a file stored in the S3-compatible storage.

        :param file_name: The name of the file stored in the bucket.
        :return: The full URL to access the file.
        """
        pass
