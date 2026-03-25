from utilities.helper_functions import fetch_s3_presigned_url, fetch_s3_presigned_url_for_download


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_owner_photo(owner):
    if not owner or not owner.profile_image:
        return None
    try:
        return fetch_s3_presigned_url(owner.profile_image)
    except Exception:
        return None


def _get_tenant_photo(tenant):
    if not tenant or not tenant.profile_image:
        return None
    try:
        return fetch_s3_presigned_url(tenant.profile_image)
    except Exception:
        return None


def _get_unit_thumbnail(unit):
    if not unit:
        return None
    try:
        pb   = unit.property_block_tower
        prop = pb.property if pb else None
        return prop._get_thumbnail() if prop else None
    except Exception:
        return None


def _get_pdf_urls(lease):
    if not lease or not lease.pdf_path:
        return None, None
    try:
        view_url     = fetch_s3_presigned_url(lease.pdf_path, file_name="agreement.pdf")
        download_url = fetch_s3_presigned_url_for_download(
            file_url=lease.pdf_path, file_name="agreement.pdf"
        )
        return view_url, download_url
    except Exception:
        return None, None


# ── Owner detail ──────────────────────────────────────────────────────────────

def serialize_owner_detail(owner):
    """Full owner profile for the detail page header."""
    return {
        "id":                   owner.id,
        "code":                 owner.code,
        "name":                 f"{owner.user.first_name} {owner.user.last_name}".strip() if owner.user else "",
        "email":                owner.email or (owner.user.email if owner.user else None),
        "contact_number":       owner.contact_number,
        "emirate_id":           owner.emirate_id,
        "visa_number":          owner.visa_number,
        "trade_license_number": owner.trade_license_number,
        "license_number":       owner.license_number,
        "license_expiry_date":  owner.license_expiry_date.isoformat() if owner.license_expiry_date else None,
        "license_issuer":       owner.license_issuer,
        "owner_number":         owner.owner_number,
        "fax_number":           owner.fax_number,
        "po_box_number":        owner.po_box_number,
        "profile_image":        _get_owner_photo(owner),
        "role":                 "Owner",
    }


# ── Owner unit row (properties table) ─────────────────────────────────────────

def serialize_owner_unit(unit, owner):
    """One row in the 'Owner Properties' table on the detail page."""
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else None

    # Pick the most recent active lease for this unit
    lease = unit.leases.filter(lease_status="ACTIVE", is_active=True).first()

    tenant    = lease.tenant if lease else None
    pdf_url, pdf_download_url = _get_pdf_urls(lease)

    return {
        # ── Unit ──────────────────────────────────────────────────
        "property_unit_id": unit.id,
        "code":             unit.code,

        # ── Property ──────────────────────────────────────────────
        "property_name":    prop.property_name if prop else unit.unit_name,
        "thumbnail":        _get_unit_thumbnail(unit),

        # ── Owner ─────────────────────────────────────────────────
        "owner_name": f"{owner.user.first_name} {owner.user.last_name}".strip() if owner.user else "",

        # ── Tenant ────────────────────────────────────────────────
        "tenant_name": (
            f"{tenant.user.first_name} {tenant.user.last_name}".strip()
            if tenant and tenant.user else None
        ),
        "tenant_profile_image": _get_tenant_photo(tenant),

        # ── Status & Lease ────────────────────────────────────────
        "tenancy_status": "Occupied" if lease else "Vacant",
        "lease_id":       lease.id if lease else None,

        # ── Agreement PDFs ────────────────────────────────────────
        "pdf_url":          pdf_url,
        "pdf_download_url": pdf_download_url,
    }
