from __future__ import annotations

import random

import boto3
from botocore.config import Config
import logging

logger = logging.getLogger("greed/shared/r2")

class R2Client:
    def __init__(self):
        logger.info("Initializing R2 client")
        self.bucket_name = "greedpfps"
        self.client = boto3.client(
            "s3",
            endpoint_url="https://c68a81f5bf0d89d9740479ab0585c751.r2.cloudflarestorage.com",
            aws_access_key_id="126fde920f75aaa52793fe95eae250d7",
            aws_secret_access_key="cf34c0352a48710dae96c340f2aef901ac0dc4b8ba86b5855676def734c33102",
            config=Config(
                s3={"addressing_style": "virtual"},
                signature_version="s3v4",
                region_name="auto"
            )
        )
        logger.info("R2 client initialized successfully")

    async def get_random_asset(self, category: str) -> str:
        """
        Get a random asset URL from a category
        """
        try:
            logger.info(f"Listing objects in category: {category}")
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"avatars/{category}/",
            )
            logger.debug(f"List objects response: {response}")

            if "Contents" not in response:
                logger.warning(f"No contents found in category {category}")
                raise Exception(f"No assets found in category {category}")

            files = [
                obj["Key"]
                for obj in response["Contents"]
                if not obj["Key"].endswith("/")
            ]
            logger.info(f"Found {len(files)} files in category {category}")

            if not files:
                logger.warning(f"No files found in category {category}")
                raise Exception(f"No assets found in category {category}")

            random_file = random.choice(files)
            logger.info(f"Selected random file: {random_file}")

            url = f"https://r2-pfps.greed.best/{random_file}"

            return url

        except Exception as e:
            logger.error(
                f"Error getting random asset from {category}: {e}", exc_info=True
            )
            raise

    async def list_folders(self, prefix: str) -> list[str]:
        """
        List all folders under a prefix
        """
        return [
            "anime",
            "cats",
            "com",
            "dogs",
            "eboy",
            "edgy",
            "egirls",
            "girls",
            "goth",
            "male",
            "matching",
            "scene",
        ]
