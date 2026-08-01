from rest_framework import serializers

from .models import SystemConfiguration


class SystemConfigurationSerializer(serializers.ModelSerializer):
    """
    Read/write shape for the in-app admin settings page.

    The Groq API key is never sent back to the browser in full — only whether
    one is set, and a masked preview. To change it, the caller submits a new
    `groq_api_key` value; to intentionally clear it, submit `clear_groq_api_key: true`.
    Omitting `groq_api_key` from a PUT leaves the stored key untouched.
    """
    groq_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    clear_groq_api_key = serializers.BooleanField(write_only=True, required=False, default=False)
    groq_api_key_set = serializers.SerializerMethodField()
    groq_api_key_preview = serializers.SerializerMethodField()

    class Meta:
        model = SystemConfiguration
        fields = [
            "groq_api_key", "clear_groq_api_key", "groq_api_key_set", "groq_api_key_preview",
            "groq_model", "groq_timeout_seconds",
            "platform_margin_percent", "support_email", "site_name",
            "payments_enabled", "subscription_price_institution",
            "subscription_price_supplier", "subscription_price_farmer",
            "subscription_period_days",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def get_groq_api_key_set(self, obj):
        return bool(obj.groq_api_key)

    def get_groq_api_key_preview(self, obj):
        if not obj.groq_api_key:
            return None
        key = obj.groq_api_key
        return f"{key[:3]}••••{key[-4:]}" if len(key) > 8 else "••••"

    def update(self, instance, validated_data):
        new_key = validated_data.pop("groq_api_key", None)
        clear_key = validated_data.pop("clear_groq_api_key", False)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if clear_key:
            instance.groq_api_key = ""
        elif new_key:
            instance.groq_api_key = new_key
        instance.save()
        return instance
