import phonenumbers
from utilities import status,constants,config
from django.http import JsonResponse
from datetime import timedelta ,datetime
from django.utils import timezone
import re
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from phonenumber_field.modelfields import PhoneNumber
from phonenumbers.phonenumberutil import region_code_for_country_code
import requests
import base64
from PIL import Image
from io import BytesIO
from utilities.jwt_token import create_jwt_token
import boto3
from botocore.exceptions import ClientError
from utilities.config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION, S3_BUCKET_NAME ,DEFAULT_HOST,PASSWORD_EXPIRY_TIME
from utilities.ses_utils import send
import logging
from django.core.files.base import ContentFile
from decimal import Decimal, InvalidOperation
import mimetypes
import csv
from django.http import HttpResponse
import platform
import pdfkit
import random
import string



def prepare_response(content={}, message='', status=status.HTTP_200_OK, paginator=None, total_records=0,pagination=None):
    resp = {
        "content": content,
        "message": message,
        "status" : status 
    }
    if pagination:
        resp["pagination"] = pagination
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



def datetime_to_epoch_millis(dt):
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return int(dt.timestamp() * 1000)



def safe_epoch_to_datetime(epoch_ms):
    try:
        return datetime.fromtimestamp(epoch_ms / 1000.0)
    except Exception:
        return None



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
    except Exception as e:
        raise e

def send_sms(contact_number, otp):
    api_key = "YOUR_API_KEY"
    sender_id = "YOUR_SENDER_ID"
    route = "YOUR_ROUTE"  
    base_url = "https://www.smsgatewayhub.com/api/mt/SendSMS"


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
                return False
        else:
            return False
    except requests.RequestException as e:
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
        return False
    

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(console_handler)

def upload_file_to_s3_base64(file_data, object_name, bucket=None):

    if not bucket:
        bucket = S3_BUCKET_NAME
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )

  
        if isinstance(file_data, str):
            if "," in file_data:
                file_data = file_data.split(",")[1]
            file_bytes = base64.b64decode(file_data)
        elif isinstance(file_data, (bytes, bytearray)):
            file_bytes = file_data
        else:
            raise ValueError("Unsupported file_data type. Must be base64 string or bytes.")

        s3_client.put_object(
            Bucket=bucket,
            Key=object_name,
            Body=file_bytes,
        )
        logger.info(f" File '{object_name}' uploaded successfully to '{bucket}'")
        return f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{object_name}"

    except ClientError as e:
        logger.error(f" Failed to upload file '{object_name}': {str(e)}")
        raise e
    except Exception as e:
        logger.error(f" Unexpected error uploading file '{object_name}': {str(e)}")
        raise e



logger = logging.getLogger(__name__)
def fetch_s3_file_as_base64(file_url):
    try:
        bucket_name = config.S3_BUCKET_NAME
        key = file_url.split(".amazonaws.com/")[1]
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
            region_name=config.AWS_REGION,
        )
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        file_bytes = response["Body"].read()
        return base64.b64encode(file_bytes).decode("utf-8")
    except ClientError as e:
        logger.error(f" ClientError fetching from S3: {e}")
        return None
    except Exception as e:
        logger.error(f" Unexpected error fetching from S3: {str(e)}") 
        return None
    




def fetch_s3_presigned_url(file_url, file_name=None, expiration=3600):
    """
    Returns a pre-signed URL for the given S3 file URL.
    Uses file_name to determine content type for inline browser view.
    expiration: time in seconds for which URL is valid (default 1 hour)
    """
    try:
        bucket_name = config.S3_BUCKET_NAME
        key = file_url.split(".amazonaws.com/")[1]

     
        if file_name:
            content_type, _ = mimetypes.guess_type(file_name)
        else:
         
            content_type = "application/octet-stream"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
            region_name=config.AWS_REGION,
        )

        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket_name,
                "Key": key,
                "ResponseContentDisposition": "inline",  
                "ResponseContentType": content_type or "application/octet-stream"
            },
            ExpiresIn=expiration
        )
        return presigned_url

    except ClientError as e:
        logger.error(f"ClientError generating presigned URL: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating presigned URL: {str(e)}")
        return None




def fetch_s3_presigned_url_for_download(file_url, file_name=None, expiration=3600):
    """
    Returns a pre-signed URL that forces file download from S3.
    """
    try:
        bucket_name = config.S3_BUCKET_NAME
        key = file_url.split(".amazonaws.com/")[1]

        if file_name:
            content_type, _ = mimetypes.guess_type(file_name)
        else:
            content_type = "application/octet-stream"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
            region_name=config.AWS_REGION,
        )

        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket_name,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{file_name or "file"}"',
                "ResponseContentType": content_type or "application/octet-stream"
            },
            ExpiresIn=expiration
        )
        return presigned_url

    except ClientError as e:
        logger.error(f"ClientError generating download presigned URL: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating download presigned URL: {str(e)}")
        return None


def get_extension_from_base64(base64_string):
    try:
        header = base64_string.split(",")[0]

        if "pdf" in header:
            return ".pdf"
        elif "jpeg" in header or "jpg" in header:
            return ".jpg"
        elif "png" in header:
            return ".png"
        elif "msword" in header:
            return ".doc"
        elif "vnd.openxmlformats-officedocument.wordprocessingml.document" in header:
            return ".docx"
        elif "vnd.openxmlformats-officedocument.spreadsheetml.sheet" in header:
            return ".xlsx"
        else:
            return None  
    except:
        return None



def safe_decimal(value):
    try:
        if value in [None, ""]:
            return None
        return Decimal(str(value))
    except InvalidOperation:
        return None  


def replace_placeholders(template_html, mapping):
    """
    Replace ${variable} placeholders using regex.
    mapping = { "var1": "value1", "var2": "value2" }
    """

    pattern = r"\$\{(.*?)\}"   

    def replacer(match):
        key = match.group(1).strip()  
        return str(mapping.get(key, match.group(0))) 

    return re.sub(pattern, replacer, template_html)





def export_to_csv(filename, field_names, data_list):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

    writer = csv.writer(response)
    writer.writerow(field_names)


    for obj in data_list:
        row = [obj.get(field, "N/A") for field in field_names]
        writer.writerow(row)
    return response




def get_pdfkit_config():
    system = platform.system()
    print("Running on:", system)  

    if system == "Windows":
        path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    elif system == "Linux":
        path = "/usr/bin/wkhtmltopdf"  
    else:
        path = "/usr/local/bin/wkhtmltopdf" 

    return pdfkit.configuration(wkhtmltopdf=path)


def generate_property_code():
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PR-{random_str}"




def generate_unique_code(prefix: str) -> str:
    """
    Generate a short unique code with a prefix.
    Example: prefix='PR' -> 
    """
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{random_part}"

def get_user_code_prefix(user_role):
    if user_role == constants.OWNER:
        return "OWN"
    elif user_role == constants.TENANT:
        return "TEN"
    elif user_role == constants.COMPANY_USER:
        return "COM"
    return "USR"




# pip install googletrans==4.0.0-rc1


# utilities/translator.py
from deep_translator import GoogleTranslator

def translate_to_arabic(text: str) -> str:
    if not text:
        return ""
    try:
        return GoogleTranslator(source="en", target="ar").translate(text)
    except Exception:
        return text  # fallback



import base64
import uuid
from django.core.files.base import ContentFile

def base64_to_image(base64_string):
    if ";base64," in base64_string:
        base64_string = base64_string.split(";base64,")[1]

    image_data = base64.b64decode(base64_string)
    file_name = f"{uuid.uuid4()}.jpg"
    return ContentFile(image_data, name=file_name)
