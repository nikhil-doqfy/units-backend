from django.db import models

class TermsAndConditions(models.Model):
    
    key = models.CharField(max_length=100) 
    title = models.CharField(max_length=255)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.key} - {self.title}"
