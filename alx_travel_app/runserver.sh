#!/bin/bash

# Activate virtual environment
source /Users/olajideojo/Desktop/alx_travel_app_0x02/venv/bin/activate

# Set PYTHONPATH to include the project directory
export PYTHONPATH=/Users/olajideojo/Desktop/alx_travel_app_0x02

# Navigate to folder containing manage.py
cd /Users/olajideojo/Desktop/alx_travel_app_0x02/alx_travel_app

# Run Django development server
python manage.py runserver