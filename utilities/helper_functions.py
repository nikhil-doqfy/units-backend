import phonenumbers
from utilities import status
from django.http import JsonResponse
from datetime import timedelta
from utilities.config import PASSWORD_EXPIRY_TIME
from django.utils import timezone
import re
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from phonenumber_field.modelfields import PhoneNumber
from phonenumbers.phonenumberutil import region_code_for_country_code
from phonenumber_field.modelfields import PhoneNumber
from utilities import constants
import requests
import base64
from PIL import Image
from io import BytesIO
from datetime import datetime
from utilities.jwt_token import create_jwt_token
from utilities.config import DEFAULT_HOST
import boto3
from botocore.exceptions import ClientError
from utilities.config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION, S3_BUCKET_NAME

import logging
def prepare_response(content={}, message='', status=status.HTTP_200_OK, paginator=None, total_records=0):
    resp = {
        "content": content,
        "message": message,
        "status" : status 
    }
    if paginator:
        resp['pagination'] = {
            'has_previous': paginator.has_previous(),
            'has_next': paginator.has_next(),
            'previous_page_number': paginator.previous_page_number() if paginator.has_previous() else None,
            'next_page_number': paginator.next_page_number() if paginator.has_next() else None,
            'page_number': paginator.number,
            'total_records': total_records
        }
    return JsonResponse(resp, status=status)


def validate_password(password):
    if len(password) < 8 or \
        not re.search('[a-z]', password) or \
        not re.search('[A-Z]', password) or \
        not re.search('[0-9]', password) or \
        not re.search("[!@#$%^&*(),.?':{}|<>]", password):
        return False
    return True
    

def is_password_expire(Userprofile):
    last_change_Date = Userprofile.password_change_timestamp
    if last_change_Date is not None : 
        expiration_date = last_change_Date + timedelta(days=PASSWORD_EXPIRY_TIME)
        if timezone.now() > expiration_date :
            return True
        return False

def validate_email(email):
    email = email.strip()
    if re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email):
        return True
    return False  

def validate_mobile(value):
    rule = re.compile(r'^\d{9}$')
    if rule.search(value):
        return True
    else:
        return False
    
# def validate_mobile(value):
#     matched_object=re.fullmatch('(0|91)?[7-9]\d{9}')
#     if matched_object:
#         return True
#     else:
#         return False

def validate_phone_number(value):
    regions = ['IN', 'US'] 
    try:
        phone_number = PhoneNumber.from_string(value)
        parsed_region = region_code_for_country_code(phone_number.country_code)
        if parsed_region not in regions:
            return {'message':constants.INVALID_CONTACT_NUMBER_FORMAT } 
        if not phonenumbers.is_valid_number(phone_number):
            return {'message':constants.INVALID_CONTACT_NUMBER}
        return True
    except:
        return {'message': constants.INVALID_CONTACT_NUMBER}


def datetime_to_epoch(dt):
    return int(dt.strftime('%s'))

def epoch_to_datetime(epoach):
    return datetime.fromtimestamp(epoach)



    
def send_email(subject, recipient_list, message="", template=None, file_path=None, bcc_emails=None, cc_emails=None):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=settings.EMAIL_HOST_USER,
        to=recipient_list,
        bcc=bcc_emails,
        cc=cc_emails,
    )
    if file_path:
        msg.attach_file(file_path)
    if template:
        message = render_to_string(template.get('path'), template.get('context'))
        msg.attach_alternative(message, "text/html")   
    try:
        msg.send()
        print("Email sent successfully")
    except Exception as e:
        print("Email sending failed:", e)
        # Optional: still return True or raise e
        raise e
# //////////////////////////////////////////////////////    
def send_sms(contact_number, otp):
 # Define your SMSGatewayHub API credentials and URL
    api_key = "YOUR_API_KEY"
    sender_id = "YOUR_SENDER_ID"
    route = "YOUR_ROUTE"  # Typically '1' for promotional, '4' for transactional, etc.
    base_url = "https://www.smsgatewayhub.com/api/mt/SendSMS"

    # Prepare the parameters for the API request
    params = {
        'APIKey': api_key,
        'senderid': sender_id,
        'channel': route,
        'DCS': 0,
        'flashsms': 0,
        'number': contact_number,
        'text': otp,
        'route': route,
    }

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            response_data = response.json()
            if response_data['ErrorMessage'] == "Success":
                return True
            else:
                print(f"Failed to send SMS: {response_data['ErrorMessage']}")
                return False
        else:
            print(f"Failed to send SMS: HTTP {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"Failed to send SMS: {e}")
        return False


def mask_string(input_string, start, end):
    masked_part = '*' * (end - start)
    masked_string = input_string[:start] + masked_part + input_string[end:]
    return masked_string


def resize_image(photo_base64, target_size_kb):
    decoded_photo = base64.b64decode(photo_base64)
    img = Image.open(BytesIO(decoded_photo))
    img = img.convert('RGB')
    target_size = target_size_kb * 1024
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    original_size = buffer.tell()
    if original_size > target_size:
        quality = int(95 * target_size / original_size)
        buffer = BytesIO()  
        img.save(buffer, format='JPEG', quality=quality)
    resized_photo = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return resized_photo


# -------------------------------------------------------------------------rest_Password



# -----------------------------------------------------------SES_reset_password------------------------------------------
# utilities/helper_functions.py

from utilities.ses_utils import send

def send_ses_email(to_email, subject, body_text, body_html):
    try:
        send(
            recipient=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text
        )
        return True
    except Exception as e:
        print("❌ SES Email send failed:", e)
        return False
# -------------------------------------------------------------------SES_Reset_password_end------------------------------


# -----------------------------------------------------------S3 AWS Congigure---------------------------------------------






# from rest_framework import status


# 🔹 Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(console_handler)


# 🔹 Upload Base64 File (decode before upload)
def upload_file_to_s3_base64(base64_data, object_name, bucket=None):
    """
    Uploads a Base64 encoded file to S3 (decodes before upload) and returns its public URL.

    :param base64_data: Base64 string of file (with or without data: prefix)
    :param object_name: Path in S3 including filename (e.g. owner_documents/1/file.pdf)
    :param bucket: Optional - S3 bucket name (default from config)
    :return: Public file URL
    """
    if not bucket:
        bucket = S3_BUCKET_NAME

    try:
        # Initialize S3 client
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )

        # Remove any Base64 header if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]

        # Decode Base64 to bytes
        file_bytes = base64.b64decode(base64_data)

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=object_name,
            Body=file_bytes,  # decoded bytes
            # ACL="public-read" # to avoid AccessControlListNotSupported error
        )

        logger.info(f"✅ File '{object_name}' uploaded successfully to '{bucket}'")

        # Return public URL
        return f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{object_name}"

    except ClientError as e:
        logger.error(f"❌ Failed to upload Base64 file '{object_name}': {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"❌ Unexpected error uploading file '{object_name}': {str(e)}")
        raise e




# --------------------------------------------------------------------------------------------------------------

