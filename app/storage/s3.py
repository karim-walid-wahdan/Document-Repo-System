import boto3
from app.core.settings import settings

def get_s3_client():
    session = boto3.session.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    return session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL)
