import boto3
from botocore.exceptions import ClientError
from app.core.settings import settings

def get_s3_client():
    session = boto3.session.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    return session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL)

def ensure_bucket_exists():
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
        return
    except ClientError as e:
        code = (e.response.get("Error", {}).get("Code") or "").lower()
        if code not in ("404", "noSuchBucket".lower(), "notfound"):
            raise
    # create if missing (LocationConstraint required if region != us-east-1)
    params = {"Bucket": settings.S3_BUCKET}
    if (settings.S3_REGION or "").lower() != "us-east-1":
        params["CreateBucketConfiguration"] = {"LocationConstraint": settings.S3_REGION}
    s3.create_bucket(**params)
