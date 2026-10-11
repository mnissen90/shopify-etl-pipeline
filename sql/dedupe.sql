-- Idempotent dedupe: keep one copy of every fully-duplicate row.
-- Safe to run after every load; deletes nothing when there are no dupes.

WITH cte AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY
                   ClientName, [Date], source_name, order_name,
                   Product_Title, Product_SKU, item_quantity,
                   shipping, [returns], gross_sales, total_discount,
                   tax, discount_codes, customer_id,
                   latitude, longitude, province, city
               ORDER BY [Date]
           ) AS row_num
    FROM dbo.ShopifyOrders
)
DELETE FROM cte WHERE row_num > 1;
