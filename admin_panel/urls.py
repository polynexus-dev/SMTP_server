from django.urls import path

app_name = 'admin_panel'

urlpatterns = [
    path('emails/', views.email_list, name='email_list'),
    path('emails/<int:pk>/', views.email_detail, name='email_detail'),
    path('emails/<int:pk>/delete/', views.email_delete, name='email_delete'),
]
