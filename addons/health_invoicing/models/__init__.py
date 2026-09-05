# Healthcare Invoicing Models
# 
# ARCHITECTURAL CHANGES (Latest):
# ================================
# 
# NEW APPROACH: Direct FSO Package Integration
# - health.fieldservice.order.package_id field replaces separate consumption model
# - Service packages are now first-class Odoo products (product.template inheritance)
# - Package consumption tracked via FSO completion, not separate records
# - Patient forms show active packages prominently with progress bars
# - Unified menu structure under main Healthcare module
#
# DEPRECATED: health.prepaid.service model
# - Kept for backward compatibility only
# - All new development uses FSO package integration
# - Migration path: FSO completion -> auto package consumption

from . import account_move
from . import account_move_line  # NEW: AR view enhancement fields (phone, aging, facility)
from . import account_payment
from . import sale_order  # NEW: Discount reason on sale order lines
from . import misa_integration
from . import healthcare_service_billing
from . import health_service_package
from . import health_payment_transaction
from . import health_prepaid_service  # DEPRECATED - use FSO package integration instead
from . import res_partner
from . import health_fieldservice_order  # NEW: Package integration fields added
from . import product_template  # NEW: Healthcare package product support
from . import product_product  # the same smart button, made valid on a variant
from . import res_config_settings  # Red Invoice toggle settings
from . import health_ar_transaction_log  # NEW: AR Transaction Log for MISA validation