from django.db import migrations

# Approximate centroid / county-HQ coordinates for Kenya's 47 counties — used to estimate
# supplier distance & delivery time and to plot supplier locations on the map. These are
# reasonable approximations (town-centre level), not survey-grade GPS.
COUNTY_COORDINATES = {
    "Mombasa": (-4.0435, 39.6682), "Kwale": (-4.1816, 39.4606), "Kilifi": (-3.5107, 39.9093),
    "Tana River": (-1.0167, 40.1000), "Lamu": (-2.2717, 40.9020), "Taita-Taveta": (-3.3966, 38.5636),
    "Garissa": (-0.4569, 39.6583), "Wajir": (1.7471, 40.0629), "Mandera": (3.9366, 41.8550),
    "Marsabit": (2.3284, 37.9899), "Isiolo": (0.3546, 37.5822), "Meru": (0.0470, 37.6499),
    "Tharaka-Nithi": (-0.3031, 37.9899), "Embu": (-0.5310, 37.4500), "Kitui": (-1.3675, 38.0106),
    "Machakos": (-1.5177, 37.2634), "Makueni": (-1.8038, 37.6244), "Nyandarua": (-0.1833, 36.5167),
    "Nyeri": (-0.4197, 36.9489), "Kirinyaga": (-0.6591, 37.3823), "Murang'a": (-0.7839, 37.1502),
    "Kiambu": (-1.1714, 36.8356), "Turkana": (3.1167, 35.6000), "West Pokot": (1.6167, 35.3833),
    "Samburu": (1.1050, 36.6906), "Trans Nzoia": (1.0157, 34.9500), "Uasin Gishu": (0.5143, 35.2698),
    "Elgeyo-Marakwet": (0.8000, 35.4833), "Nandi": (0.1833, 35.1167), "Baringo": (0.4667, 35.9667),
    "Laikipia": (0.2027, 36.7820), "Nakuru": (-0.3031, 36.0800), "Narok": (-1.0833, 35.8667),
    "Kajiado": (-1.8500, 36.7833), "Kericho": (-0.3667, 35.2833), "Bomet": (-0.7833, 35.3333),
    "Kakamega": (0.2827, 34.7519), "Vihiga": (0.0833, 34.7167), "Bungoma": (0.5667, 34.5667),
    "Busia": (0.4608, 34.1115), "Siaya": (0.0607, 34.2881), "Kisumu": (-0.0917, 34.7680),
    "Homa Bay": (-0.5273, 34.4571), "Migori": (-1.0634, 34.4731), "Kisii": (-0.6817, 34.7680),
    "Nyamira": (-0.5633, 34.9358), "Nairobi": (-1.2921, 36.8219),
}


def seed_coordinates(apps, schema_editor):
    County = apps.get_model("core", "County")
    for name, (lat, lng) in COUNTY_COORDINATES.items():
        County.objects.filter(name=name).update(latitude=lat, longitude=lng)


def unseed_coordinates(apps, schema_editor):
    County = apps.get_model("core", "County")
    County.objects.update(latitude=None, longitude=None)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_county_latitude_county_longitude"),
    ]

    operations = [
        migrations.RunPython(seed_coordinates, unseed_coordinates),
    ]
