-- Warehouse table for Shopify order line items, shipping, and refunds.
-- One row per line item / shipping line / refund line item.

CREATE TABLE dbo.ShopifyOrders (
    ClientName      NVARCHAR(255)  NOT NULL,
    [Date]          DATETIME2      NOT NULL,
    source_name     NVARCHAR(255)  NULL,
    order_name      NVARCHAR(100)  NULL,
    Product_Title   NVARCHAR(500)  NULL,
    Product_SKU     NVARCHAR(100)  NULL,
    item_quantity   INT            NULL,
    shipping        DECIMAL(18, 2) NULL,
    [returns]       DECIMAL(18, 2) NULL,
    gross_sales     DECIMAL(18, 2) NULL,
    total_discount  DECIMAL(18, 2) NULL,
    tax             DECIMAL(18, 2) NULL,
    discount_codes  NVARCHAR(500)  NULL,
    customer_id     NVARCHAR(100)  NULL,
    latitude        FLOAT          NULL,
    longitude       FLOAT          NULL,
    province        NVARCHAR(255)  NULL,
    city            NVARCHAR(255)  NULL,
    line_items_price DECIMAL(18, 2) NULL  -- derived: gross - discount + returns + shipping + tax
);

CREATE INDEX IX_ShopifyOrders_Client_Date
    ON dbo.ShopifyOrders (ClientName, [Date]);
