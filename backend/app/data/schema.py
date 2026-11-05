"""SQLite tables for the supplied synthetic data pack.

The tables mirror the CSV columns one to one (see data/raw/README.md), so the
seed loader can stay generic. Journey tables (sessions, consents, orders, KYC)
are added by their own modules later.
"""

from __future__ import annotations

from sqlalchemy import Column, Date, Integer, MetaData, String, Table

metadata = MetaData()

products = Table(
    "products",
    metadata,
    Column("product_id", String, primary_key=True),
    Column("category", String, nullable=False),
    Column("product_name", String, nullable=False),
    Column("description", String, nullable=False),
    Column("unit", String, nullable=False),
    Column("price_min_inr_per_month", Integer, nullable=False),
    Column("price_max_inr_per_month", Integer, nullable=False),
    Column("one_time_setup_inr", Integer, nullable=False),
    Column("min_contract_months", Integer, nullable=False),
    Column("available_city_tiers", String, nullable=False),  # ";"-separated
    Column("min_employees", Integer, nullable=False),
    Column("min_sites", Integer, nullable=False),
    Column("requires_gstin", String, nullable=False),  # "Y" / "N"
    Column("requires_one_of", String),  # "|"-separated, may be empty
    Column("typical_install_days", Integer, nullable=False),
    Column("target_segments", String, nullable=False),  # ";"-separated
)

gstin_registry = Table(
    "gstin_registry",
    metadata,
    Column("gstin", String, primary_key=True),
    Column("legal_name", String, nullable=False),
    Column("trade_name", String, nullable=False),
    Column("constitution", String, nullable=False),
    Column("principal_place_of_business", String, nullable=False),
    Column("state", String, nullable=False),
    Column("registration_date", Date, nullable=False),
    Column("status", String, nullable=False),  # Active / Cancelled / Suspended
)

udyam_registry = Table(
    "udyam_registry",
    metadata,
    Column("udyam_number", String, primary_key=True),
    Column("enterprise_name", String, nullable=False),
    Column("enterprise_type", String, nullable=False),
    Column("major_activity", String, nullable=False),
    Column("nic_description", String, nullable=False),
    Column("state", String, nullable=False),
    Column("city", String, nullable=False),
    Column("date_of_registration", Date, nullable=False),
)

historical_leads = Table(
    "historical_leads",
    metadata,
    Column("lead_id", String, primary_key=True),
    Column("created_date", Date, nullable=False),
    Column("lead_source", String, nullable=False),
    Column("business_name", String, nullable=False),
    Column("business_type", String, nullable=False),
    Column("segment", String, nullable=False),
    Column("city", String, nullable=False),
    Column("city_tier", Integer, nullable=False),
    Column("state", String, nullable=False),
    Column("preferred_language", String, nullable=False),
    Column("employee_count", Integer, nullable=False),
    Column("num_sites", Integer, nullable=False),
    Column("annual_turnover_band", String, nullable=False),
    Column("has_gstin", String, nullable=False),
    Column("gstin", String),
    Column("has_udyam", String, nullable=False),
    Column("udyam_number", String),
    Column("current_internet", String, nullable=False),
    Column("current_provider", String, nullable=False),
    Column("monthly_telecom_spend_inr", Integer, nullable=False),
    Column("products_of_interest", String, nullable=False),
    Column("contact_name", String, nullable=False),
    Column("contact_role", String, nullable=False),
    Column("stage_reached", String, nullable=False),
    Column("outcome", String, nullable=False),
    Column("drop_reason", String),
    Column("contacted_date", Date),
    Column("needs_assessed_date", Date),
    Column("quote_accepted_date", Date),
    Column("kyc_complete_date", Date),
    Column("activated_date", Date),
    Column("days_lead_to_activation", Integer),
    Column("customer_follow_up_calls", Integer, nullable=False),
    Column("bundle_products", String),
    Column("monthly_bundle_value_inr", Integer),
    Column("one_time_setup_inr", Integer),
    Column("contract_months", Integer),
    Column("churned_within_6_months", String),
    Column("nps_score", Integer),
    Column("acquisition_cost_inr", Integer, nullable=False),
)

# CSV file name -> table, in load order.
SEED_FILES: dict[str, Table] = {
    "product_catalogue.csv": products,
    "mock_gstin_registry.csv": gstin_registry,
    "mock_udyam_registry.csv": udyam_registry,
    "smb_leads.csv": historical_leads,
}
