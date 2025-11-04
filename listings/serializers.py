import re
from rest_framework import serializers
from .models import Listing, Booking, Review, Payments
import uuid

class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = '__all__'
        
    def validate_title(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be a positive number.")
        return value
    

class BookingSerializer(serializers.ModelSerializer):
    
    listing = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.all())
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    email = serializers.EmailField(required=False, allow_null=True)
    
    class Meta:
        model = Booking
        fields = ['booking_id', 'listing', 'user', 'email', 'status', 'created_at']
        read_only_fields = ['booking_id', 'status', 'created_at']

    def validate_user(self, value):
        """Allow user to be None if unauthenticated."""
        request = self.context.get('request')
        if request and not request.user.is_authenticated:
            return None
        return value


    def validate_status(self, value):
        if value not in ['pending', 'confirmed', 'canceled']:
            raise serializers.ValidationError("Status must be one of: pending, confirmed, canceled.")
        return value
    
class ReviewSerializer(serializers.ModelSerializer):
    
    listing = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.all())
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Review
        fields = ['review_id', 'listing', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['review_id', 'created_at']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def validate_comment(self, value):
        if len(value) < 10:
            raise serializers.ValidationError("Comment must be at least 10 characters long.")
        return value


class PaymentCreateSerializer(serializers.Serializer):
    
    class Meta:
        model = Payments
        fields = ['payment_id', 'booking', 'amount', 'status', 'trxn_reference', 'created_at', 'updated_at']
        read_only_fields = ['payment_id', 'status', 'created_at', 'updated_at']
        
    booking_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    
    def validate_user(self, value):
        """Allow user to be None if unauthenticated."""
        request = self.context.get('request')
        if request and not request.user.is_authenticated:
            return None
        return value

    def validate_booking_id(self, value):
        if not Booking.objects.filter(booking_id=value).exists():
            raise serializers.ValidationError("Booking with this ID does not exist.")
        return value
     
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be a positive number.")
        return value