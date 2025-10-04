-- SQL Migration Script: Add Address Autocomplete Fields to res_partner
-- Run this manually in your PostgreSQL database for odoo18

-- Add address_search field
ALTER TABLE res_partner
ADD COLUMN IF NOT EXISTS address_search VARCHAR;

-- Add partner_latitude field
ALTER TABLE res_partner
ADD COLUMN IF NOT EXISTS partner_latitude NUMERIC(10,7);

-- Add partner_longitude field
ALTER TABLE res_partner
ADD COLUMN IF NOT EXISTS partner_longitude NUMERIC(10,7);

-- Add date_localization field
ALTER TABLE res_partner
ADD COLUMN IF NOT EXISTS date_localization DATE;

-- Verify columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'res_partner'
  AND column_name IN ('address_search', 'partner_latitude', 'partner_longitude', 'date_localization')
ORDER BY column_name;
