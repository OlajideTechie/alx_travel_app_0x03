from django.urls import path, re_path
from . import views
from rest_framework import permissions


urlpatterns = [
    path('listings/', views.ListingListCreateView.as_view(), name='listing-list-create'),
    path ('bookings/', views.BookingCreateView.as_view(), name='create-booking'),
    path('reviews/', views.ReviewCreateView.as_view(), name='review-create'),
    path('payments/initiate/', views.ChapaPaymentInitView.as_view(), name='chapa-payment-init'),
    path('chapa/verify/<str:reference>/', views.ChapaPaymentVerifyView.as_view(), name='chapa-payment-verify'),
    #path('payments/webhook/', views.ChapaPaymentWebhookView.as_view(), name='chapa-payment-webhook'),
   
]