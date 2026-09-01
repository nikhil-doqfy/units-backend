# utilities/ses_utils.py

import boto3
from botocore.exceptions import ClientError
from logging import getLogger
from utilities import config

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

logger = getLogger(__name__)
client = boto3.client(
    'sesv2',
    region_name=config.SES_AWS_REGION,
    aws_access_key_id=config.SES_AWS_ACCESS_KEY,
    aws_secret_access_key=config.SES_AWS_SECRET_KEY
)

def send(recipient, subject, body_text, body_html, cc=None, bcc=None):
    try:
        
        response = client.send_email(
            FromEmailAddress=config.EMAIL_SENDER,
            Destination={
                'ToAddresses': [recipient],
                'CcAddresses': cc or [],
                'BccAddresses': bcc or []
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
        logger.info(f" Email sent to {recipient}, MessageId: {response['MessageId']}")
        return response
    except ClientError as e:
        logger.error(f" SES Send Error: {e.response['Error']['Message']}")
        raise e

def send_invoice_email(recipient, subject, body_text, body_html, pdf_bytes, pdf_filename):
    try:
        msg = MIMEMultipart("mixed")

        msg["Subject"] = subject
        msg["From"] = config.EMAIL_SENDER
        msg["To"] = recipient

        body = MIMEMultipart("alternative")
        body.attach(MIMEText(body_text, "plain", "utf-8"))
        body.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(body)

        pdf_attachment = MIMEApplication(
            pdf_bytes,
            _subtype="pdf"
        )

        pdf_attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=pdf_filename
        )

        msg.attach(pdf_attachment)

        response = client.send_email(
            FromEmailAddress=config.EMAIL_SENDER,
            Destination={
                "ToAddresses": [recipient]
            },
            Content={
                "Raw": {
                    "Data": msg.as_bytes()
                }
            }
        )

        logger.info(
            f" Invoice email sent to {recipient}, "
            f"MessageId: {response['MessageId']}"
        )

        return response

    except ClientError as e:
        logger.error(
            f" Invoice email SES Send Error: "
            f"{e.response['Error']['Message']}"
        )
        raise e