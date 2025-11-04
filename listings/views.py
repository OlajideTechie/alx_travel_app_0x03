import json
import requests
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from .serializers import PaymentCreateSerializer, BookingSerializer, ReviewSerializer, ListingSerializer
from .models import Payments, Booking, Listing, Review
from .Utils.utils import generate_payment_reference 
from django.conf import settings
from .tasks import send_booking_confirmation_email 
from django.db import connection
import logging
import uuid
from django.db import models
from .Utils.throttling import CustomScopedRateThrottle

logger = logging.getLogger(__name__)

CHAPA_SECRET_KEY = settings.CHAPA_SECRET_KEY


class ListingListCreateView(APIView):
    """API view to list all listings or create a new listing."""
    permission_classes = [AllowAny]

    def get(self, request):
        listings = Listing.objects.all()
        serializer = ListingSerializer(listings, many=True)
        return Response({"message": "Listings retrieved successfully.", "data": serializer.data})

    def post(self, request):
        serializer = ListingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Listing created successfully.", "data": serializer.data},
                            status=status.HTTP_201_CREATED)
        logger.error(f"Listing creation failed. Errors: {serializer.errors}")
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class BookingCreateView(APIView):
    """API view to create a booking for a listing."""
    permission_classes = [AllowAny]
    throttle_classes = [CustomScopedRateThrottle]
    throttle_scope = 'booking'

    def _trigger_email(self, user_email, booking_id):
        """Helper method to trigger sending booking confirmation email asynchronously."""
        try:
            send_booking_confirmation_email.delay(user_email, booking_id)
            logger.info(f"Celery task triggered for booking ID {booking_id} -> {user_email}")
        except Exception:
            logger.exception(f"Failed to trigger Celery email task for booking {booking_id}")

    def post(self, request):
        serializer = BookingSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            try:
                booking = serializer.save()

                # Determine user email (authenticated user or guest)
                user_email = None
                if booking.user and getattr(booking.user, 'email', None):
                    user_email = booking.user.email
                elif serializer.validated_data.get('email'):
                    user_email = serializer.validated_data['email']

                if user_email:
                    self._trigger_email(user_email, booking.booking_id)
                else:
                    logger.warning(f"No email provided for booking ID {booking.id}. Email will not be sent.")

                return Response(
                    {
                        "message": "Booking created successfully. A confirmation email will be sent shortly.",
                        "data": serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )

            except Exception:
                logger.exception("Error while saving booking")
                return Response(
                    {"error": "Internal server error while creating booking."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f"Booking creation failed. Errors: {serializer.errors}")
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class ReviewCreateView(APIView):
    """API view to create a review for a listing."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Review created successfully.", "data": serializer.data},
                            status=status.HTTP_201_CREATED)
        logger.error(f"Review creation failed. Errors: {serializer.errors}")
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class ChapaPaymentInitView(APIView):
    """API view to initialize a payment with Chapa."""
    permission_classes = [AllowAny]
    throttle_classes = [CustomScopedRateThrottle]
    throttle_scope = 'payment'

    def _create_payment_record(self, booking_id, amount, payment_reference, chapa_ref):
        """Helper method to create a payment record in the database."""
        Payments.objects.create(
            booking_id=booking_id,
            amount=amount,
            trxn_reference=payment_reference,
            chapa_reference=chapa_ref,
        )
        logger.info(f"Chapa payment record created: ETB{amount} | Ref: {payment_reference} | ChapaRef: {chapa_ref}")

    def post(self, request, *args, **kwargs):
        amount = request.data.get("amount")
        email = request.data.get("email")
        booking_id = request.data.get("booking_id")

        payment_reference = f"CHAP-{uuid.uuid4().hex[:10].upper()}"

        payload = {
            "amount": amount,
            "currency": "ETB",
            "email": email,
            "tx_ref": payment_reference,
            "callback_url": "http://localhost:8000/chapa/verify/",
            #"return_url": "http://localhost:8000/success",
        }

        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}

        try:
            response = requests.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                checkout_url = response_data["data"]["checkout_url"]
                chapa_ref = checkout_url.split("/")[-1]

                self._create_payment_record(booking_id, amount, payment_reference, chapa_ref)

                return Response({
                    "message": "Payment initialized successfully.",
                    "payment_url": checkout_url,
                    "merchant_reference": payment_reference,
                    "chapa_reference": chapa_ref
                }, status=status.HTTP_200_OK)

            logger.error(f"Chapa payment initialization failed: {response_data}")
            return Response({"error": "Failed to initialize payment", "details": response_data},
                            status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.exception("Error initializing Chapa payment")
            return Response({"error": "Internal server error while initializing payment."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ChapaPaymentVerifyView(APIView):
    """API view to verify a payment with Chapa."""
    permission_classes = [AllowAny]

    def get(self, request, reference, *args, **kwargs):
        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}

        possible_refs = [reference]
        if not reference.startswith("CHAP-"):
            possible_refs.append(f"CHAP-{reference}")

        try:
            for ref in possible_refs:
                response = requests.get(
                    f"https://api.chapa.co/v1/transaction/verify/{ref}",
                    headers=headers
                )
                response_data = response.json()

                logger.debug(f"Verifying payment reference: {ref}")

                if response.status_code == 200 and response_data.get('status') == 'success':
                    payment_data = response_data['data']
                    tx_ref = payment_data.get('tx_ref')
                    chapa_ref = payment_data.get('reference')
                    chapa_status = payment_data.get('status')

                    payment = Payments.objects.filter(
                        models.Q(trxn_reference__in=[ref, tx_ref]) |
                        models.Q(chapa_reference__in=[ref, chapa_ref])
                    ).first()

                    if payment:
                        payment.status = chapa_status or payment.status
                        if hasattr(payment, "chapa_response"):
                            payment.chapa_response = payment_data
                        payment.save()
                        
                        
                        """Send payment status email asynchronously"""
                        try:
                            booking = payment.booking
                            user_email = None
                            if booking and booking.user and getattr(booking.user, 'email', None):
                                user_email = booking.user.email
                            elif getattr(booking, 'email', None):
                                user_email = booking.email

                            if user_email:
                                from .tasks import send_payment_status_email
                                send_payment_status_email.delay(
                                    user_email,
                                    chapa_status or "unknown",
                                    payment.amount,
                                    payment.trxn_reference
                                )
                            else:
                                logger.warning(f"No email found for payment {payment.trxn_reference}")

                        except Exception:
                            logger.exception("Failed to queue payment status email")

                        logger.info(f"Chapa payment verified: {chapa_ref} ({payment.status})")
                        return Response({
                            "message": "Payment verified successfully.",
                            "reference": chapa_ref, 
                            "tx_ref": tx_ref,
                            "status": payment.status
                        }, status=status.HTTP_200_OK)

                    logger.warning(f"No payment found for tx_ref={tx_ref} or reference={chapa_ref}")
                    return Response({"error": "Payment record not found."}, status=status.HTTP_404_NOT_FOUND)

            logger.error(f"Verification failed for all references: {possible_refs}")
            return Response({
                "error": "Failed to verify payment.",
                "details": response_data
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.exception("Error verifying Chapa payment")
            return Response({"error": "Internal server error while verifying payment."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ChapaPaymentWebhookView(APIView):
    """API view to handle Chapa payment webhook notifications."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            payload = request.data
            logger.info(f"Received Chapa webhook payload: {payload}")

            chapa_reference = payload.get("reference")
            status_chapa = payload.get("status")

            if not chapa_reference:
                logger.error("Chapa webhook missing 'reference' field")
                return Response({"error": "Missing 'reference' in webhook payload"}, status=status.HTTP_400_BAD_REQUEST)

            payment = Payments.objects.filter(chapa_reference=chapa_reference).first()
            if not payment:
                logger.error(f"No payment found for Chapa reference: {chapa_reference}")
                return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

            payment.status = status_chapa or payment.status
            if hasattr(payment, "chapa_response"):
                payment.chapa_response = payload
            payment.save()

            logger.info(f"Chapa webhook processed successfully for reference: {chapa_reference} with status: {payment.status}")
            return Response({"message": "Webhook processed successfully."}, status=status.HTTP_200_OK)

        except Exception:
            logger.exception("Error processing Chapa webhook")
            return Response({"error": "Internal server error while processing webhook."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ServiceHealthCheck(APIView):
    """API view to check the health status of the service."""
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # check: database connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")

            return Response(
                {"status": "Service is up and running."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Health check failed")
            return Response(
                {"status": "Service is unhealthy.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
   
      