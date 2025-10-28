from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_booking_confirmation_email(user_email, booking_id):
    subject = "Booking Confirmation"
    message = f"Your booking (ID: {booking_id}) has been confirmed. Thank you for choosing us!"
    email_from = settings.EMAIL_HOST_USER
    
    
    send_mail(subject, message, email_from, [user_email])
    logger.info(f"Booking confirmation email sent to {user_email}")
    return f"Booking confirmation email sent to {user_email}"