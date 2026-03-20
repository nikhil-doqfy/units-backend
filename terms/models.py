from django.db import models
from property_management.models import Country, Base


class TermCategory(Base):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class TermsAndConditions(Base):
    key = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="terms"
    )

    category = models.ForeignKey(
        TermCategory,
        on_delete=models.CASCADE,
        related_name="terms"
    )

    class Meta:
        unique_together = ("key", "country", "category")
        ordering = ["country", "category", "key"]

    def __str__(self):
        return f"{self.country.code} - {self.category.code} - {self.key}"