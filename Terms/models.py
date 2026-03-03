from django.db import models


class TermsAndConditions(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    effective_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title