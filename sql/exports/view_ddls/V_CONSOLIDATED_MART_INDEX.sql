create or replace view V_CONSOLIDATED_MART_INDEX(
	MART_NAME,
	BUSINESS_AREA,
	GRAIN,
	CONTENTS
) as
SELECT
    'V_ORDER_MART' AS MART_NAME,
    'ORDERS' AS BUSINESS_AREA,
    'JOBNUMBER + ESTIMATENUMBER' AS GRAIN,
    'Order header, totals, price changes, quote totals, job UDFs' AS CONTENTS

UNION ALL
SELECT
    'V_COMPONENT_MART',
    'COMPONENTS',
    'JOBNUMBER + ESTIMATENUMBER + COMPONENTNUMBER',
    'Component details, quantity pricing, unit cost, component UDFs'

UNION ALL
SELECT
    'V_PURCHASING_MART_CLEAN',
    'PURCHASING',
    'PONUMBER + ITEMNUMBER',
    'PO header, line items, receipts, dropship, images'

UNION ALL
SELECT
    'V_VENDOR_MART_CLEAN',
    'VENDORS',
    'VENDORID + PRODUCTID',
    'Vendor balances, products, pricing'

UNION ALL
SELECT
    'V_MATERIAL_RFQ_MART',
    'MATERIALS / RFQ',
    'JOBNUMBER + COMPONENTNUMBER + MATERIALCODE',
    'Requisitions enriched with RFQ data'

UNION ALL
SELECT
    'V_PRODUCTION_MART',
    'PRODUCTION',
    'JOBNUMBER + COMPONENTNUMBER + PROCESSCODE',
    'Production job activity and schedule metrics'

UNION ALL
SELECT
    'V_PROCESS_MART_CLEAN',
    'PROCESS',
    'NOT FINALIZED',
    'Still has row multiplication; keep as exploratory until grain is resolved';;
