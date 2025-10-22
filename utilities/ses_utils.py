# utilities/ses_utils.py

import boto3
from botocore.exceptions import ClientError
from logging import getLogger
from utilities import config

logger = getLogger(__name__)

client = boto3.client(
    'sesv2',
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY,
    aws_secret_access_key=config.AWS_SECRET_KEY
)


def send(recipient, subject, body_text, body_html):
    """
    Send a simple email using AWS SES (v2).
    """
    try:
        response = client.send_email(
            FromEmailAddress=config.EMAIL_SENDER,
            Destination={
                'ToAddresses': [recipient]
            },
            Content={
                'Simple': {
                    'Subject': {'Data': subject},
                    'Body': {
                        'Text': {'Data': body_text},
                        'Html': {'Data': body_html}
                    }
                }
            }
        )
        logger.info(f"✅ Email sent to {recipient}, MessageId: {response['MessageId']}")
        return response
    except ClientError as e:
        logger.error(f"❌ SES Send Error: {e.response['Error']['Message']}")
        raise e