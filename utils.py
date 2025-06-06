import smtplib
import os 
import uuid
import requests
from PIL import Image
from email.message import EmailMessage
from dotenv import load_dotenv
from flask import current_app
from werkzeug.utils import secure_filename

load_dotenv()

def convert_to_webp(image_file, app_root, logger=None):
    try:
        unique_id = uuid.uuid4().hex[:8]
        base_name = secure_filename(image_file.filename.rsplit('.', 1)[0])
        webp_filename = f"{base_name}_{unique_id}.webp"
        image_path = os.path.join(app_root, 'static/images', webp_filename)

        img = Image.open(image_file)
        img.convert("RGB").save(image_path, "webp", optimize=True, quality=80)

        return webp_filename
    except Exception as e:
        if logger:
            logger.error("Image conversion failed", exc_info=True)
        return None
    
def send_custom_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = os.getenv("MAIL_USERNAME")
        msg['To'] = to_email
        msg.set_content(body)

        with smtplib.SMTP(os.getenv("MAIL_SERVER"), int(os.getenv("MAIL_PORT"))) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
            smtp.send_message(msg)
            smtp.quit()
            current_app.logger.info(f"Status update email sent to {to_email}")

    except Exception as e:
        current_app.logger.error(f"Email sending failed: {e}", exc_info=True)

def send_email_password_reset(to_email, new_password):
    try: 
        msg = EmailMessage()
        msg['Subject'] = "Password Reset - Your New Password"
        msg['From'] = os.getenv("MAIL_USERNAME")
        msg['To'] = to_email
        msg.set_content(f"Your new password is: {new_password}\n\nPlease login and change your password immediately.")

        with smtplib.SMTP(os.getenv("MAIL_SERVER"), int(os.getenv("MAIL_PORT"))) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
            smtp.send_message(msg)
    except Exception as e:
        current_app.logger.error(f"send_email_password_reset failed: {e}")
        raise        

def send_contact_email(from_name, from_email, message):
    try:
        msg = EmailMessage()
        msg['Subject'] = f"New Contact Form Message from {from_name}"
        msg['From'] = os.getenv("MAIL_USERNAME")
        msg['To'] = os.getenv("MAIL_USERNAME")  # Send to site admin
        msg.set_content(f"From: {from_name} <{from_email}>\n\n{message}")

        with smtplib.SMTP(os.getenv("MAIL_SERVER"), int(os.getenv("MAIL_PORT"))) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
            smtp.send_message(msg)
    except Exception as e:
        current_app.logger.error(f"Contact email sending failed: {e}")
        raise
    
def send_order_email(to_email, order_id):
    try:
        msg = EmailMessage()
        msg['Subject'] = f"Order Confirmation - {order_id}"
        msg['From'] = os.getenv("MAIL_USERNAME")
        msg['To'] = to_email
        msg.set_content(f"Thank you for placing your order! Your Order ID is {order_id}.")

        with smtplib.SMTP(os.getenv("MAIL_SERVER"), int(os.getenv("MAIL_PORT"))) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD"))
            smtp.send_message(msg)
        print("Email sent successfully")
    except Exception as e:
        current_app.logger.error(f"Email sending failed: {e}")

def send_order_sms(phone, order_id):
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        "authorization": os.getenv("FAST2SMS_API_KEY"),
        "route": "v3",
        "sender_id": "TXTIND",
        "message": f"Order {order_id} placed successfully!",
        "language": "english",
        "flash": 0,
        "numbers": phone
    }
    headers = {
        'cache-control': "no-cache"
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        print("SMS sent:", response.text)
    except Exception as e:
        current_app.logger.error("SMS sending failed:", e)
