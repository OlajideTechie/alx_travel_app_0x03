from django.contrib import admin
from django.urls import path, re_path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from listings.views import ChapaPaymentInitView

schema_view = get_schema_view(
    openapi.Info(
        title="Alx Travel App API",
        default_version='v1.0',
        description="API documentation for Alx Travel App",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    #path('api/initiate-payment/', ChapaPaymentInitView.as_view(), name='chapa-payment-init'),
    path('api/', include('listings.urls')),
    path('api/auth/', include('rest_framework.urls')),


    # Swagger
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
