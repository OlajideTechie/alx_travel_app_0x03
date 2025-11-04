from django.contrib.auth import get_user_model
from listings.models import Listing, Booking, Review

def run():
    User = get_user_model()

    """Seed the database with initial data for Listings, Bookings, and Reviews."""
    # Create a test user
    user, _ = User.objects.get_or_create(
        email="testuser@example.com",
        defaults={"username": "testuser", "password": "password123"}
    )
    user.set_password("password123")
    user.save()
    
    # Create sample listings
    listings_data = [
        {"title": "Luxury Villa", "description": "5-star villa with pool", "price": 500, "location": "Abuja"},
        {"title": "Beachside Apartment", "description": "2-bedroom apartment near the beach", "price": 200, "location": "Lagos"},
        {"title": "Budget Hostel", "description": "Shared hostel room for backpackers", "price": 50, "location": "Nairobi"}
    ]

    listings = []
    for data in listings_data:
        listing, _ = Listing.objects.get_or_create(**data)
        listings.append(listing)

    # Create sample bookings
    Booking.objects.get_or_create(listing=listings[0], user=user, status="confirmed")
    Booking.objects.get_or_create(listing=listings[1], user=user, status="pending")

    # Create sample reviews
    Review.objects.get_or_create(listing=listings[0], user=user, rating=5, comment="Amazing stay!")
    Review.objects.get_or_create(listing=listings[1], user=user, rating=4, comment="Great location, would recommend.")