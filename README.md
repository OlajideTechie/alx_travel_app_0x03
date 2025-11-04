## 🔄 Background Task Management with Celery, RabbitMQ & SendGrid

This project integrates **Celery** and **RabbitMQ** to manage asynchronous tasks — such as sending booking confirmation emails via **SendGrid**.

### 🧠 Features
- Background task execution using Celery workers
- RabbitMQ as the message broker
- Email notifications handled asynchronously via SendGrid
- Structured logging for all background jobs

### 🏃‍♀️ How It Works
1. User makes a booking request.
2. Django view saves the booking and triggers a Celery task.
3. Celery worker picks up the job from RabbitMQ.
4. Email is sent via SendGrid — all asynchronously!

### Start RabbitMQ Brker service
```bash
  brew services start rabbitmq

### 🐇 Start Celery Worker
```bash
celery -A alx_travel_app worker -l info

