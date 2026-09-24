"""
Real DRF serializer for LeadViewSet (the first lead endpoint converted off
prepare_response/is_request_authenticated -- see the DRF migration plan).
"""
from rest_framework import serializers


class LeadSerializer(serializers.Serializer):
    """Delegates to lead.views._serialize_lead()/_serialize_lead_with_lease(),
    which already assemble the nested unit/property/owner shape other code
    depends on -- reusing them here keeps that shape identical rather than
    re-deriving it field by field. Pass with_lease=True in the serializer's
    context (retrieve) to include lease_id/lease_stage; list omits it,
    matching lead_view's previous GET-list-vs-GET-single behavior.
    """

    def to_representation(self, instance):
        from lead.views import _serialize_lead, _serialize_lead_with_lease
        if self.context.get("with_lease"):
            return _serialize_lead_with_lease(instance)
        return _serialize_lead(instance)
