from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    bio = models.TextField(blank=True, null=True) 
    profile_photo = models.ImageField(verbose_name= 'Photo de profil' )

