from django.db import models


class County(models.Model):
    """
    Reference data: Kenya's 47 counties, used to populate the county dropdown
    everywhere a user picks/edits a county (registration, institution profile,
    etc.) instead of relying on free-text entry. Also carries an approximate
    centroid (latitude/longitude) used to estimate supplier distance & delivery
    time, and to plot supplier locations on the map — see core/geo.py.
    Seeded by data migrations.
    """
    name = models.CharField(max_length=64, unique=True)
    code = models.PositiveSmallIntegerField(unique=True, null=True, blank=True, help_text="Official county code (1–47).")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "counties"

    def __str__(self):
        return self.name
