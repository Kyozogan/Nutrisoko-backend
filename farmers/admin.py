from django.contrib import admin
from .models import Farmer, DemandSignal, SupplyCommitment

admin.site.register(Farmer)
admin.site.register(DemandSignal)
admin.site.register(SupplyCommitment)
