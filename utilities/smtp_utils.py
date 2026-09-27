# utilities/smtp_utils.py
#
# SMTP counterpart to ses_utils.py -- same send()/send_invoice_email() surface,
# selected instead of SES when EMAIL_CHANNEL_PREFERENCE=SMTP (see
# helper_functions.send_ses_email, the shared dispatcher both channels sit behind).

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging import getLogger

from utilities import config

logger = getLogger(__name__)


def _connect():
    server = smtplib.SMTP(config.SMTP_EMAIL_HOST, config.SMTP_EMAIL_PORT, timeout=15)
    server.starttls()
    server.login(config.SMTP_EMAIL_HOST_USER, config.SMTP_EMAIL_HOST_PASSWORD)
    return server


def send(recipient, subject, body_text, body_html, cc=None, bcc=None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_EMAIL_HOST_USER
    msg["To"] = recipient
    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.attach(MIMEText(body_text, "plain", config.EMAIL_CHARSET))
    msg.attach(MIMEText(body_html, "html", config.EMAIL_CHARSET))

    all_recipients = [recipient] + (cc or []) + (bcc or [])

    try:
        server = _connect()
        try:
            server.sendmail(config.SMTP_EMAIL_HOST_USER, all_recipients, msg.as_string())
        finally:
            server.quit()
        logger.info(f" Email sent to {recipient} via SMTP")
    except smtplib.SMTPException as e:
        logger.error(f" SMTP Send Error: {e}")
        raise e


def send_invoice_email(recipient, subject, body_text, body_html, pdf_bytes, pdf_filename):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_EMAIL_HOST_USER
    msg["To"] = recipient

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(body_text, "plain", config.EMAIL_CHARSET))
    body.attach(MIMEText(body_html, "html", config.EMAIL_CHARSET))
    msg.attach(body)

    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=pdf_filename)
    msg.attach(pdf_attachment)

    try:
        server = _connect()
        try:
            server.sendmail(config.SMTP_EMAIL_HOST_USER, [recipient], msg.as_string())
        finally:
            server.quit()
        logger.info(f" Invoice email sent to {recipient} via SMTP")
    except smtplib.SMTPException as e:
        logger.error(f" Invoice email SMTP Send Error: {e}")
        raise e
