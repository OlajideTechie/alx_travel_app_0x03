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
import logging
import uuid
logger = logging.getLogger(__name__)


CHAPA_SECRET_KEY = settings.CHAPA_SECRET_KEY


class ListingListCreateView(APIView):
    """List all listings or create a new one."""
    permission_classes = [AllowAny]

    def get(self, request):
        listings = Listing.objects.all()
        serializer = ListingSerializer(listings, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ListingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookingCreateView(APIView):
    """Create a booking for a listing."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BookingSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            try:
                booking = serializer.save()

                # Determine user email (authenticated or guest)
                user_email = None
                if booking.user and getattr(booking.user, 'email', None):
                    user_email = booking.user.email
                elif serializer.validated_data.get('email'):
                    user_email = serializer.validated_data['email']

                # Trigger Celery background email task
                if user_email:
                    try:
                        send_booking_confirmation_email.delay(user_email, booking.booking_id)
                        logger.info(f"Celery task triggered for booking ID {booking.booking_id} -> {user_email}")
                    except Exception as e:
                        logger.error(f"Failed to trigger Celery email task for booking {booking.id}: {str(e)}", exc_info=True)
                else:
                    logger.warning(f"No email provided for booking ID {booking.id}. Email will not be sent.")

                return Response(
                    {
                        "message": "Booking created successfully. A confirmation email will be sent shortly.",
                        "data": serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )

            except Exception as e:
                logger.error(f"Error while saving booking: {str(e)}", exc_info=True)
                return Response(
                    {"error": "Internal server error while creating booking."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Validation errors
        logger.error(f"Booking creation failed. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReviewCreateView(APIView):
    """Create a review for a listing."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class ChapaPaymentInitView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        amount = request.data.get("amount")
        email = request.data.get("email")
        booking_id = request.data.get("booking_id")

        # Generate your own merchant tx_ref
        payment_reference = f"CHAP-{uuid.uuid4().hex[:10].upper()}"

        payload = {
            "amount": amount,
            "currency": "ETB",
            "email": email,
            "tx_ref": payment_reference,
            "callback_url": "http://localhost:8000/chapa/verify/",
            "return_url": "http://localhost:8000/success",
        }

        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}

        try:
            response = requests.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                checkout_url = response_data["data"]["checkout_url"]
                # extract Chapa-assigned ref (APxxxx) from URL
                chapa_ref = checkout_url.split("/")[-1]

                Payments.objects.create(
                    booking_id=booking_id,
                    amount=amount,
                    trxn_reference=payment_reference,
                    chapa_reference=chapa_ref,  # save it!
                )

                logger.info(f"Chapa payment initiated: ETB{amount} | Ref: {payment_reference} | ChapaRef: {chapa_ref}")

                return Response({
                    "payment_url": checkout_url,
                    "merchant_reference": payment_reference,
                    "chapa_reference": chapa_ref
                }, status=status.HTTP_200_OK)

            logger.error(f"Chapa payment initialization failed: {response_data}")
            return Response({"error": "Failed to initialize payment", "details": response_data},
                            status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Error initializing Chapa payment")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@method_decorator(csrf_exempt, name='dispatch')
class ChapaPaymentVerifyView(APIView):
    permission_classes = [AllowAny]
    """View to verify a payment with Chapa."""

    def get(self, request, reference, *args, **kwargs):
        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}

        # Try both possible forms (CHAP-xxxx and APxxxx)
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

                print("🔍 Verifying this reference:", ref)

                if response.status_code == 200 and response_data.get('status') == 'success':
                    payment_data = response_data['data']
                    tx_ref = payment_data.get('tx_ref')
                    chapa_ref = payment_data.get('reference')
                    chapa_status = payment_data.get('status')

                    # Try to find payment by any known reference
                    payment = Payments.objects.filter(
                        models.Q(trxn_reference__in=[ref, tx_ref]) |
                        models.Q(chapa_reference__in=[ref, chapa_ref])
                    ).first()

                    if payment:
                        payment.status = chapa_status or payment.status
                        # Optional: store Chapa’s raw data if you have such a field
                        if hasattr(payment, "chapa_response"):
                            payment.chapa_response = payment_data
                        payment.save()

                        logger.info(f"Chapa payment verified: {chapa_ref} ({payment.status})")
                        return Response({
                            "message": "Payment verified successfully.",
                            "reference": chapa_ref,
                            "tx_ref": tx_ref,
                            "status": payment.status
                        }, status=status.HTTP_200_OK)

                    logger.warning(f"No payment found for tx_ref={tx_ref} or reference={chapa_ref}")
                    return Response({"error": "Payment record not found."}, status=status.HTTP_404_NOT_FOUND)

            # If all attempts failed
            logger.error(f"Verification failed for all refs: {possible_refs}")
            return Response({
                "error": "Failed to verify payment.",
                "details": response_data
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("💥 Error verifying Chapa payment")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        

@method_decorator(csrf_exempt, name='dispatch')
class ChapaPaymentWebhookView(APIView):
    permission_classes = [AllowAny]   

    def post(self, request, *args, **kwargs):
        try:
            payload = request.data
            logger.info(f"Received Chapa webhook: {payload}")

            chapa_reference = payload.get("reference")
            status_chapa = payload.get("status")

            if not chapa_reference:
                logger.error("Chapa webhook missing 'reference'")
                return Response({"error": "Missing reference"}, status=status.HTTP_400_BAD_REQUEST)

            payment = Payments.objects.filter(chapa_reference=chapa_reference).first()
            if not payment:
                logger.error(f"No payment found for Chapa reference: {chapa_reference}")
                return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

            payment.status = status_chapa or payment.status
            # Optional: store Chapa’s raw data if you have such a field
            if hasattr(payment, "chapa_response"):
                payment.chapa_response = payload
            payment.save()

            logger.info(f"Chapa webhook processed: {chapa_reference} ({payment.status})")
            return Response({"message": "Webhook processed successfully."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Error processing Chapa webhook")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
