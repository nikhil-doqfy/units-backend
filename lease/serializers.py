from utilities.helper_functions import fetch_s3_presigned_url


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tenant_photo(tenant):
    if not tenant or not tenant.profile_image:
        return None
    try:
        return fetch_s3_presigned_url(tenant.profile_image)
    except Exception:
        return None


def _get_property_thumbnail(unit):
    if not unit:
        return None
    try:
        pb = unit.property_block_tower
        return pb.property._get_thumbnail() if pb and pb.property else None
    except Exception:
        return None


# ── Lease ─────────────────────────────────────────────────────────────────────

def serialize_lease(lease):
    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else None

    unit_owners = []
    if unit:
        for o in unit.unit_owners.select_related("owner__user").all():
            unit_owners.append({
                "id":                   o.id,
                "owner_id":             o.owner_id,
                "name":                 f"{o.owner.user.first_name} {o.owner.user.last_name}".strip() if o.owner and o.owner.user else None,
                "email":                o.owner.email if o.owner else None,
                "contact_number":       o.owner.contact_number if o.owner else None,
                "emirates_id":          o.owner.emirate_id if o.owner else None,
                "nationality":          o.owner.nationality if o.owner else None,
                "owner_number":         o.owner.owner_number if o.owner else None,
                "trade_license_number": o.owner.trade_license_number if o.owner else None,
                "license_number":       o.owner.license_number if o.owner else None,
                "license_expiry_date":  o.owner.license_expiry_date.isoformat() if o.owner and o.owner.license_expiry_date else None,
                "license_issuer":       o.owner.license_issuer if o.owner else None,
                "fax_number":           o.owner.fax_number if o.owner else None,
                "po_box_number":        o.owner.po_box_number if o.owner else None,
            })

    return {
        "id":       lease.id,
        "code":     lease.code,
        "platform": lease.platform,

        # ── Property ──────────────────────────────────────────────
        "property": {
            "id":         prop.id if prop else None,
            "name":       prop.property_name if prop else None,
            "thumbnail":  _get_property_thumbnail(unit),
            "block_id":   pb.id if pb else None,
            "block_name": pb.block_name if pb else None,
        },

        # ── Unit ──────────────────────────────────────────────────
        "unit": {
            "id":         unit.id if unit else None,
            "name":       unit.unit_name if unit else None,
            "size":       str(unit.unit_size) if unit and unit.unit_size else None,
            "land_no":    unit.land_no if unit else None,
            "dm_no":      unit.dm_no if unit else None,
            "unit_usage": unit.unit_usage if unit else None,
            "unit_type":  unit.unit_type if unit else None,
            "sub_type":   unit.sub_type if unit else None,
            "makani_no":  unit.makani_no if unit else None,
            "floor_no":   unit.floor_no if unit else None,
            "owners":     unit_owners,
        },

        # ── Tenant ────────────────────────────────────────────────
        "tenant": {
            "id":              t.id if t else None,
            "code":            t.code if t else None,
            "name":            f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else None,
            "email":           t.user.email if t and t.user else None,
            "contact":         t.contact_number if t else None,
            "emirates_id":     t.emirate_id if t else None,
            "nationality":     t.nationality if t else None,
            "address_line_1":  t.address_line_1 if t else None,
            "address_line_2":  t.address_line_2 if t else None,
            "passport_number": t.passport_number if t else None,
            "passport_expiry": str(t.passport_expiry_datetime)[:10] if t and t.passport_expiry_datetime else None,
            "visa_number":     t.visa_number if t else None,
            "visa_expiry":     str(t.visa_expiry_datetime)[:10] if t and t.visa_expiry_datetime else None,
            "is_onboarding":   t.is_onboarding if t else False,
        },

        # ── Lease Info ────────────────────────────────────────────
        "lease_status": lease.lease_status,
        "lease_stage":  lease.lease_stage,
        "remarks":      lease.remarks,
        "pdf_path":     lease.pdf_path,
        "shell_and_core": lease.shell_and_core,

        # ── Dates ─────────────────────────────────────────────────
        "dates": {
            "start_date":       str(lease.start_date)[:10] if lease.start_date else None,
            "end_date":         str(lease.end_date)[:10] if lease.end_date else None,
            "grace_start_date": str(lease.grace_start_date)[:10] if lease.grace_start_date else None,
            "grace_end_date":   str(lease.grace_end_date)[:10] if lease.grace_end_date else None,
        },

        # ── Financials ────────────────────────────────────────────
        "financials": {
            "annual_amount":        lease.annual_amount,
            "actual_annual_amount": lease.actual_annual_amount,
            "booking_amount":       lease.booking_amount,
            "maintenance_charges":  lease.maintenance_charges,
            "rent":                 lease.rent,
            "security_deposit":     lease.security_deposit,
            "commission":           lease.commission,
            "notice_period":        lease.notice_period,
            "discount":             lease.discount,
            "contract_amount":      lease.contract_amount,
            "payment_count":        lease.payment_count,
        },
    }


# ── Tenant Lease (tenant-facing list) ─────────────────────────────────────────

def serialize_tenant_lease(lease):
    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else None

    return {
        "id":           lease.id,
        "code":         lease.code,
        "lease_status": lease.lease_status,
        "lease_stage":  lease.lease_stage,

        # ── Tenant ────────────────────────────────────────────────
        "tenant": {
            "id":             t.id if t else None,
            "code":           t.code if t else None,
            "name":           f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else None,
            "photo":          _get_tenant_photo(t),
            "email":          t.email if t else None,
            "contact_number": t.contact_number if t else None,
            "emirates_id":    t.emirate_id if t else None,
            "nationality":    t.nationality if t else None,
        },

        # ── Property ──────────────────────────────────────────────
        "property": {
            "id":         prop.id if prop else None,
            "name":       prop.property_name if prop else None,
            "thumbnail":  _get_property_thumbnail(unit),
            "block_id":   pb.id if pb else None,
            "block_name": pb.block_name if pb else None,
        },

        # ── Unit ──────────────────────────────────────────────────
        "unit": {
            "id":   unit.id if unit else None,
            "name": unit.unit_name if unit else None,
        },

        # ── Dates ─────────────────────────────────────────────────
        "dates": {
            "start_date": str(lease.start_date)[:10] if lease.start_date else None,
            "end_date":   str(lease.end_date)[:10] if lease.end_date else None,
        },

        # ── Financials ────────────────────────────────────────────
        "financials": {
            "rent":          lease.rent,
            "annual_amount": lease.annual_amount,
        },
    }
