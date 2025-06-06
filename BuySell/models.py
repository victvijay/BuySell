
from flask_sqlalchemy import SQLAlchemy
from cryptography.fernet import Fernet 
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash 
from datetime import datetime

import os

db = SQLAlchemy()
load_dotenv()

FERNET_KEY = os.environ.get("FERNET_KEY") or Fernet.generate_key()
cipher = Fernet(FERNET_KEY)

class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_title = db.Column(db.String(100))
    tagline = db.Column(db.String(150))
    support_phone = db.Column(db.String(20))
    support_email = db.Column(db.String(100))
    footer_note = db.Column(db.String(200))
    email_notify = db.Column(db.Boolean, default=True) 
    sms_notify = db.Column(db.Boolean, default=True)    

class RazorpayConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key_id = db.Column(db.String(100), nullable=False)
    key_secret_encrypted = db.Column(db.LargeBinary, nullable=False)

    def set_secret(self, secret):
        self.key_secret_encrypted = cipher.encrypt(secret.encode())

    def get_secret(self):
        return cipher.decrypt(self.key_secret_encrypted).decode()

class RazorpayTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    razorpay_signature = db.Column(db.String(255))
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship('Order', backref=db.backref('transaction', uselist=False))

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class SubCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

    category = db.relationship('Category', backref=db.backref('subcategories', lazy=True))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column((db.Float), nullable=False)
    stock = db.Column((db.Integer), nullable=False)
    image = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    sub_category_id = db.Column(db.Integer, db.ForeignKey('sub_category.id'),nullable=True)
    category = db.relationship('Category', backref='products')
    sub_category = db.relationship('SubCategory', backref='products')
    description = db.Column(db.Text) 
    shipping_charge = db.Column(db.Float, default=0.0)     
    
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # store hashed password
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True)

    def set_password(self, plain_password):
        self.password_hash = generate_password_hash(plain_password)

    def check_password(self, plain_password):
        return check_password_hash(self.password_hash, plain_password)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(20), unique=True, nullable=False)
    invoice_number = db.Column(db.String(100), unique=True, nullable=True) 
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    address = db.Column(db.Text, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    shipping_total = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), default='Pending')  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    courier_service = db.Column(db.String(100))
    tracking_number = db.Column(db.String(100))
    estimated_delivery = db.Column(db.Date)
    shipment_date = db.Column(db.Date)   
    delivered_date = db.Column(db.Date)  

    customer = db.relationship('Customer', backref='orders')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    order = db.relationship('Order', backref='items')
    product = db.relationship('Product')

class Address(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    line1 = db.Column(db.String(255), nullable=False)
    line2 = db.Column(db.String(255))
    landmark = db.Column(db.String(100))
    phone = db.Column(db.String(15), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)

    customer = db.relationship('Customer', backref='addresses')

class MailConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mail_server = db.Column(db.String(120))
    mail_port = db.Column(db.Integer)
    mail_use_tls = db.Column(db.Boolean, default=True)
    mail_username = db.Column(db.String(120))
    mail_password_encrypted = db.Column(db.LargeBinary)

    def set_password(self, raw_password, fernet_key):
        f = Fernet(fernet_key)
        self.mail_password_encrypted = f.encrypt(raw_password.encode())

    def get_password(self, fernet_key):
        f = Fernet(fernet_key)
        return f.decrypt(self.mail_password_encrypted).decode()
