-- ============================================================
-- Financial Tables for Quantitative RAG (WF4 Text-to-SQL)
-- Creates realistic financial data for benchmark testing
-- All tables include tenant_id for multi-tenancy
-- ============================================================

-- Drop existing tables to ensure correct schema (re-runnable)
DROP TABLE IF EXISTS sales_data CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS balance_sheet CASCADE;
DROP TABLE IF EXISTS financials CASCADE;

-- 1. Income Statement / Financials
CREATE TABLE IF NOT EXISTS financials (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'benchmark',
    company_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    fiscal_year INT NOT NULL,
    period TEXT NOT NULL,  -- 'Q1','Q2','Q3','Q4','FY'
    revenue NUMERIC(15,2),
    cost_of_goods_sold NUMERIC(15,2),
    gross_profit NUMERIC(15,2),
    operating_expenses NUMERIC(15,2),
    research_development NUMERIC(15,2),
    selling_general_admin NUMERIC(15,2),
    operating_income NUMERIC(15,2),
    interest_income NUMERIC(15,2),
    interest_expense NUMERIC(15,2),
    other_income NUMERIC(15,2),
    income_before_tax NUMERIC(15,2),
    tax_expense NUMERIC(15,2),
    net_income NUMERIC(15,2),
    basic_eps NUMERIC(10,4),
    diluted_eps NUMERIC(10,4),
    shares_outstanding BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, company_id, fiscal_year, period)
);
CREATE INDEX IF NOT EXISTS idx_fin_tenant_company ON financials(tenant_id, company_id);
CREATE INDEX IF NOT EXISTS idx_fin_year ON financials(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_fin_period ON financials(period);

-- 2. Balance Sheet
CREATE TABLE IF NOT EXISTS balance_sheet (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'benchmark',
    company_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    fiscal_year INT NOT NULL,
    cash_and_equivalents NUMERIC(15,2),
    short_term_investments NUMERIC(15,2),
    accounts_receivable NUMERIC(15,2),
    inventory NUMERIC(15,2),
    total_current_assets NUMERIC(15,2),
    property_plant_equipment NUMERIC(15,2),
    goodwill NUMERIC(15,2),
    intangible_assets NUMERIC(15,2),
    total_assets NUMERIC(15,2),
    accounts_payable NUMERIC(15,2),
    short_term_debt NUMERIC(15,2),
    accrued_liabilities NUMERIC(15,2),
    total_current_liabilities NUMERIC(15,2),
    long_term_debt NUMERIC(15,2),
    total_liabilities NUMERIC(15,2),
    common_stock NUMERIC(15,2),
    retained_earnings NUMERIC(15,2),
    total_stockholders_equity NUMERIC(15,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, company_id, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_bs_tenant_company ON balance_sheet(tenant_id, company_id);
CREATE INDEX IF NOT EXISTS idx_bs_date ON balance_sheet(as_of_date DESC);

-- 3. Sales Data (transaction-level)
CREATE TABLE IF NOT EXISTS sales_data (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'benchmark',
    company_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    region TEXT NOT NULL,
    country TEXT,
    quarter TEXT NOT NULL,
    fiscal_year INT NOT NULL,
    quantity INT,
    unit_price NUMERIC(10,2),
    amount NUMERIC(15,2),
    discount NUMERIC(10,2) DEFAULT 0,
    cost NUMERIC(15,2),
    gross_margin NUMERIC(10,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sales_tenant ON sales_data(tenant_id, company_id);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales_data(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_region ON sales_data(region);
CREATE INDEX IF NOT EXISTS idx_sales_year ON sales_data(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_sales_quarter ON sales_data(quarter);
CREATE INDEX IF NOT EXISTS idx_sales_category ON sales_data(category);

-- 4. Employees
CREATE TABLE IF NOT EXISTS employees (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'benchmark',
    company_id TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    title TEXT NOT NULL,
    hire_date DATE,
    salary NUMERIC(12,2),
    bonus NUMERIC(12,2),
    stock_options INT DEFAULT 0,
    region TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, company_id, employee_id)
);
CREATE INDEX IF NOT EXISTS idx_emp_tenant ON employees(tenant_id, company_id);
CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(department);
CREATE INDEX IF NOT EXISTS idx_emp_region ON employees(region);

-- 5. Products catalog
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'benchmark',
    company_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    launch_date DATE,
    unit_cost NUMERIC(10,2),
    list_price NUMERIC(10,2),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, company_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_prod_tenant ON products(tenant_id, company_id);
CREATE INDEX IF NOT EXISTS idx_prod_category ON products(category);

-- ============================================================
-- SEED DATA: 3 companies, 4 years, realistic financials
-- ============================================================

-- Company 1: TechVision Inc (large tech company)
-- Company 2: GreenEnergy Corp (mid-cap energy company)
-- Company 3: HealthPlus Labs (biotech startup growing fast)

-- === FINANCIALS (FY data for 3 companies x 4 years) ===

INSERT INTO financials (tenant_id, company_id, company_name, fiscal_year, period,
    revenue, cost_of_goods_sold, gross_profit, operating_expenses,
    research_development, selling_general_admin, operating_income,
    interest_income, interest_expense, other_income, income_before_tax,
    tax_expense, net_income, basic_eps, diluted_eps, shares_outstanding)
VALUES
-- TechVision Inc - FY 2020-2023
('benchmark','techvision','TechVision Inc',2020,'FY', 4250000000, 1487500000, 2762500000, 1700000000, 850000000, 850000000, 1062500000, 12500000, 45000000, 8000000, 1038000000, 218000000, 820000000, 8.20, 7.95, 100000000),
('benchmark','techvision','TechVision Inc',2021,'FY', 5100000000, 1734000000, 3366000000, 1938000000, 1020000000, 918000000, 1428000000, 15000000, 42000000, 10000000, 1411000000, 296000000, 1115000000, 11.15, 10.80, 100000000),
('benchmark','techvision','TechVision Inc',2022,'FY', 5865000000, 1935450000, 3929550000, 2229000000, 1173000000, 1056000000, 1700550000, 25000000, 38000000, 5000000, 1692550000, 355000000, 1337550000, 13.38, 12.95, 100000000),
('benchmark','techvision','TechVision Inc',2023,'FY', 6745000000, 2158400000, 4586600000, 2563000000, 1349000000, 1214000000, 2023600000, 45000000, 35000000, 12000000, 2045600000, 429000000, 1616600000, 16.17, 15.65, 100000000),
-- TechVision quarterly 2023
('benchmark','techvision','TechVision Inc',2023,'Q1', 1552350000, 496752000, 1055598000, 589690000, 310390000, 279300000, 465908000, 10000000, 9000000, 3000000, 469908000, 98681000, 371227000, 3.71, 3.59, 100000000),
('benchmark','techvision','TechVision Inc',2023,'Q2', 1619400000, 518208000, 1101192000, 615372000, 323880000, 291492000, 485820000, 11000000, 9000000, 3000000, 490820000, 103072000, 387748000, 3.88, 3.75, 100000000),
('benchmark','techvision','TechVision Inc',2023,'Q3', 1721750000, 550960000, 1170790000, 654265000, 344350000, 309915000, 516525000, 12000000, 8500000, 3000000, 523025000, 109835000, 413190000, 4.13, 4.00, 100000000),
('benchmark','techvision','TechVision Inc',2023,'Q4', 1851500000, 592480000, 1259020000, 703673000, 370300000, 333373000, 555347000, 12000000, 8500000, 3000000, 561847000, 117988000, 443859000, 4.44, 4.30, 100000000),

-- GreenEnergy Corp - FY 2020-2023
('benchmark','greenenergy','GreenEnergy Corp',2020,'FY', 1800000000, 1080000000, 720000000, 504000000, 180000000, 324000000, 216000000, 5000000, 28000000, 3000000, 196000000, 41200000, 154800000, 3.10, 2.98, 50000000),
('benchmark','greenenergy','GreenEnergy Corp',2021,'FY', 2160000000, 1252800000, 907200000, 583200000, 216000000, 367200000, 324000000, 6000000, 25000000, 4000000, 309000000, 64900000, 244100000, 4.88, 4.70, 50000000),
('benchmark','greenenergy','GreenEnergy Corp',2022,'FY', 2808000000, 1544400000, 1263600000, 702000000, 281000000, 421000000, 561600000, 8000000, 22000000, 6000000, 553600000, 116300000, 437300000, 8.75, 8.42, 50000000),
('benchmark','greenenergy','GreenEnergy Corp',2023,'FY', 3650000000, 1935000000, 1715000000, 876000000, 365000000, 511000000, 839000000, 12000000, 18000000, 8000000, 841000000, 176600000, 664400000, 13.29, 12.80, 50000000),
-- GreenEnergy quarterly 2023
('benchmark','greenenergy','GreenEnergy Corp',2023,'Q1', 803000000, 425590000, 377410000, 192720000, 80300000, 112420000, 184690000, 2500000, 4500000, 2000000, 184690000, 38785000, 145905000, 2.92, 2.81, 50000000),
('benchmark','greenenergy','GreenEnergy Corp',2023,'Q2', 876500000, 464545000, 411955000, 210360000, 87650000, 122710000, 201595000, 3000000, 4500000, 2000000, 202095000, 42440000, 159655000, 3.19, 3.07, 50000000),
('benchmark','greenenergy','GreenEnergy Corp',2023,'Q3', 949000000, 503170000, 445830000, 227760000, 94900000, 132860000, 218070000, 3200000, 4500000, 2000000, 218770000, 45941000, 172829000, 3.46, 3.33, 50000000),
('benchmark','greenenergy','GreenEnergy Corp',2023,'Q4', 1021500000, 541395000, 480105000, 245160000, 102150000, 143010000, 234945000, 3300000, 4500000, 2000000, 235745000, 49507000, 186238000, 3.72, 3.59, 50000000),

-- HealthPlus Labs - FY 2020-2023
('benchmark','healthplus','HealthPlus Labs',2020,'FY', 320000000, 176000000, 144000000, 128000000, 96000000, 32000000, 16000000, 1000000, 12000000, 500000, 5500000, 1155000, 4345000, 0.17, 0.16, 25000000),
('benchmark','healthplus','HealthPlus Labs',2021,'FY', 480000000, 252000000, 228000000, 172800000, 134400000, 38400000, 55200000, 1500000, 10000000, 1000000, 47700000, 10017000, 37683000, 1.51, 1.45, 25000000),
('benchmark','healthplus','HealthPlus Labs',2022,'FY', 768000000, 391680000, 376320000, 261120000, 199680000, 61440000, 115200000, 3000000, 8000000, 2000000, 112200000, 23562000, 88638000, 3.55, 3.41, 25000000),
('benchmark','healthplus','HealthPlus Labs',2023,'FY', 1152000000, 553000000, 599000000, 380160000, 288000000, 92160000, 218840000, 5000000, 6000000, 3000000, 220840000, 46376000, 174464000, 6.98, 6.71, 25000000),
-- HealthPlus quarterly 2023
('benchmark','healthplus','HealthPlus Labs',2023,'Q1', 253440000, 121652000, 131788000, 83635000, 63360000, 20275000, 48153000, 1000000, 1500000, 750000, 48403000, 10165000, 38238000, 1.53, 1.47, 25000000),
('benchmark','healthplus','HealthPlus Labs',2023,'Q2', 276480000, 132710000, 143770000, 91238000, 69120000, 22118000, 52532000, 1200000, 1500000, 750000, 52982000, 11126000, 41856000, 1.67, 1.61, 25000000),
('benchmark','healthplus','HealthPlus Labs',2023,'Q3', 299520000, 143770000, 155750000, 98842000, 74880000, 23962000, 56908000, 1300000, 1500000, 750000, 57458000, 12066000, 45392000, 1.82, 1.75, 25000000),
('benchmark','healthplus','HealthPlus Labs',2023,'Q4', 322560000, 154868000, 167692000, 106445000, 80640000, 25805000, 61247000, 1500000, 1500000, 750000, 61997000, 13019000, 48978000, 1.96, 1.88, 25000000)
ON CONFLICT (tenant_id, company_id, fiscal_year, period) DO NOTHING;

-- === BALANCE SHEET (year-end snapshots) ===

INSERT INTO balance_sheet (tenant_id, company_id, company_name, as_of_date, fiscal_year,
    cash_and_equivalents, short_term_investments, accounts_receivable, inventory,
    total_current_assets, property_plant_equipment, goodwill, intangible_assets, total_assets,
    accounts_payable, short_term_debt, accrued_liabilities, total_current_liabilities,
    long_term_debt, total_liabilities, common_stock, retained_earnings, total_stockholders_equity)
VALUES
-- TechVision
('benchmark','techvision','TechVision Inc','2020-12-31',2020, 1200000000, 500000000, 850000000, 150000000, 2700000000, 1500000000, 800000000, 400000000, 5400000000, 450000000, 200000000, 350000000, 1000000000, 600000000, 1600000000, 1000000000, 2800000000, 3800000000),
('benchmark','techvision','TechVision Inc','2021-12-31',2021, 1500000000, 600000000, 1020000000, 165000000, 3285000000, 1650000000, 850000000, 380000000, 6165000000, 510000000, 180000000, 400000000, 1090000000, 550000000, 1640000000, 1000000000, 3525000000, 4525000000),
('benchmark','techvision','TechVision Inc','2022-12-31',2022, 1800000000, 750000000, 1173000000, 175000000, 3898000000, 1800000000, 900000000, 360000000, 6958000000, 587000000, 150000000, 460000000, 1197000000, 500000000, 1697000000, 1000000000, 4261000000, 5261000000),
('benchmark','techvision','TechVision Inc','2023-12-31',2023, 2200000000, 900000000, 1349000000, 185000000, 4634000000, 2000000000, 950000000, 340000000, 7924000000, 675000000, 120000000, 530000000, 1325000000, 450000000, 1775000000, 1000000000, 5149000000, 6149000000),
-- GreenEnergy
('benchmark','greenenergy','GreenEnergy Corp','2020-12-31',2020, 350000000, 100000000, 360000000, 200000000, 1010000000, 1200000000, 200000000, 100000000, 2510000000, 270000000, 150000000, 180000000, 600000000, 500000000, 1100000000, 500000000, 910000000, 1410000000),
('benchmark','greenenergy','GreenEnergy Corp','2021-12-31',2021, 450000000, 120000000, 432000000, 220000000, 1222000000, 1400000000, 220000000, 90000000, 2932000000, 313000000, 130000000, 210000000, 653000000, 450000000, 1103000000, 500000000, 1329000000, 1829000000),
('benchmark','greenenergy','GreenEnergy Corp','2022-12-31',2022, 650000000, 180000000, 562000000, 250000000, 1642000000, 1650000000, 250000000, 80000000, 3622000000, 386000000, 100000000, 260000000, 746000000, 380000000, 1126000000, 500000000, 1996000000, 2496000000),
('benchmark','greenenergy','GreenEnergy Corp','2023-12-31',2023, 900000000, 250000000, 730000000, 280000000, 2160000000, 1950000000, 280000000, 70000000, 4460000000, 484000000, 80000000, 320000000, 884000000, 300000000, 1184000000, 500000000, 2776000000, 3276000000),
-- HealthPlus
('benchmark','healthplus','HealthPlus Labs','2020-12-31',2020, 80000000, 20000000, 64000000, 48000000, 212000000, 150000000, 50000000, 80000000, 492000000, 48000000, 40000000, 32000000, 120000000, 200000000, 320000000, 100000000, 72000000, 172000000),
('benchmark','healthplus','HealthPlus Labs','2021-12-31',2021, 120000000, 30000000, 96000000, 56000000, 302000000, 180000000, 55000000, 75000000, 612000000, 60000000, 35000000, 40000000, 135000000, 180000000, 315000000, 100000000, 197000000, 297000000),
('benchmark','healthplus','HealthPlus Labs','2022-12-31',2022, 200000000, 50000000, 154000000, 65000000, 469000000, 220000000, 60000000, 70000000, 819000000, 78000000, 25000000, 52000000, 155000000, 150000000, 305000000, 100000000, 414000000, 514000000),
('benchmark','healthplus','HealthPlus Labs','2023-12-31',2023, 320000000, 80000000, 230000000, 75000000, 705000000, 280000000, 65000000, 65000000, 1115000000, 110000000, 20000000, 70000000, 200000000, 120000000, 320000000, 100000000, 695000000, 795000000)
ON CONFLICT (tenant_id, company_id, as_of_date) DO NOTHING;

-- === PRODUCTS ===

INSERT INTO products (tenant_id, company_id, product_id, product_name, category, launch_date, unit_cost, list_price)
VALUES
-- TechVision products
('benchmark','techvision','TV-CLOUD-001','CloudSync Pro','Cloud Services','2019-03-15', 12.00, 49.99),
('benchmark','techvision','TV-CLOUD-002','CloudSync Enterprise','Cloud Services','2020-06-01', 25.00, 129.99),
('benchmark','techvision','TV-AI-001','VisionAI Platform','AI/ML','2021-01-10', 50.00, 299.99),
('benchmark','techvision','TV-AI-002','VisionAI Edge','AI/ML','2022-04-20', 35.00, 199.99),
('benchmark','techvision','TV-SEC-001','CyberShield','Security','2020-09-01', 8.00, 39.99),
('benchmark','techvision','TV-DATA-001','DataLake Pro','Data Analytics','2021-07-15', 20.00, 89.99),
-- GreenEnergy products
('benchmark','greenenergy','GE-SOLAR-001','SolarMax 400W','Solar Panels','2019-06-01', 120.00, 349.99),
('benchmark','greenenergy','GE-SOLAR-002','SolarMax 600W','Solar Panels','2021-03-15', 180.00, 499.99),
('benchmark','greenenergy','GE-WIND-001','WindTurbo 5kW','Wind Turbines','2020-01-20', 2500.00, 7999.99),
('benchmark','greenenergy','GE-BATT-001','PowerVault 10kWh','Battery Storage','2021-09-01', 1800.00, 5499.99),
('benchmark','greenenergy','GE-BATT-002','PowerVault 20kWh','Battery Storage','2022-06-15', 3200.00, 9999.99),
('benchmark','greenenergy','GE-MGMT-001','GridManager Pro','Energy Management','2022-01-10', 15.00, 79.99),
-- HealthPlus products
('benchmark','healthplus','HP-DX-001','GenomeScan 1.0','Diagnostics','2019-04-01', 200.00, 899.99),
('benchmark','healthplus','HP-DX-002','GenomeScan 2.0','Diagnostics','2021-08-15', 150.00, 749.99),
('benchmark','healthplus','HP-TX-001','ImmunoBoost','Therapeutics','2020-11-01', 45.00, 299.99),
('benchmark','healthplus','HP-TX-002','NeuroShield','Therapeutics','2022-03-20', 80.00, 499.99),
('benchmark','healthplus','HP-DG-001','MedAssist AI','Digital Health','2022-07-01', 10.00, 59.99),
('benchmark','healthplus','HP-DG-002','PatientHub','Digital Health','2023-01-15', 5.00, 29.99)
ON CONFLICT (tenant_id, company_id, product_id) DO NOTHING;

-- === SALES DATA (quarterly by product x region) ===
-- 3 companies x ~6 products x 4 regions x 4 years x 4 quarters = ~1152 rows

-- Helper: generate sales for TechVision
INSERT INTO sales_data (tenant_id, company_id, product_id, product_name, category, region, country, quarter, fiscal_year, quantity, unit_price, amount, discount, cost, gross_margin)
SELECT
    'benchmark', 'techvision', p.product_id, p.product_name, p.category,
    r.region, r.country,
    'Q' || q.q, y.yr,
    base_qty * (1 + (y.yr - 2020) * 0.15 + q.q * 0.02 + r.mult * 0.1)::int as quantity,
    p.list_price * (1 - 0.05 * r.mult),
    (base_qty * (1 + (y.yr - 2020) * 0.15 + q.q * 0.02 + r.mult * 0.1)::int) * p.list_price * (1 - 0.05 * r.mult),
    (base_qty * (1 + (y.yr - 2020) * 0.15 + q.q * 0.02 + r.mult * 0.1)::int) * p.list_price * 0.05 * r.mult,
    (base_qty * (1 + (y.yr - 2020) * 0.15 + q.q * 0.02 + r.mult * 0.1)::int) * p.unit_cost,
    ROUND(((p.list_price - p.unit_cost) / p.list_price)::numeric, 4)
FROM
    (VALUES ('TV-CLOUD-001','CloudSync Pro','Cloud Services',49.99,12.00,5000),
            ('TV-CLOUD-002','CloudSync Enterprise','Cloud Services',129.99,25.00,1200),
            ('TV-AI-001','VisionAI Platform','AI/ML',299.99,50.00,800),
            ('TV-AI-002','VisionAI Edge','AI/ML',199.99,35.00,1500),
            ('TV-SEC-001','CyberShield','Security',39.99,8.00,8000),
            ('TV-DATA-001','DataLake Pro','Data Analytics',89.99,20.00,3000))
        AS p(product_id, product_name, category, list_price, unit_cost, base_qty),
    (VALUES (1),(2),(3),(4)) AS q(q),
    (VALUES (2020),(2021),(2022),(2023)) AS y(yr),
    (VALUES ('North America','United States',1.0),
            ('Europe','Germany',0.7),
            ('Asia Pacific','Japan',0.5),
            ('Latin America','Brazil',0.3))
        AS r(region, country, mult)
WHERE p.list_price IS NOT NULL;

-- Sales for GreenEnergy
INSERT INTO sales_data (tenant_id, company_id, product_id, product_name, category, region, country, quarter, fiscal_year, quantity, unit_price, amount, discount, cost, gross_margin)
SELECT
    'benchmark', 'greenenergy', p.product_id, p.product_name, p.category,
    r.region, r.country,
    'Q' || q.q, y.yr,
    (base_qty * (1 + (y.yr - 2020) * 0.20 + q.q * 0.03 + r.mult * 0.1))::int as quantity,
    p.list_price * (1 - 0.03 * r.mult),
    ((base_qty * (1 + (y.yr - 2020) * 0.20 + q.q * 0.03 + r.mult * 0.1))::int) * p.list_price * (1 - 0.03 * r.mult),
    ((base_qty * (1 + (y.yr - 2020) * 0.20 + q.q * 0.03 + r.mult * 0.1))::int) * p.list_price * 0.03 * r.mult,
    ((base_qty * (1 + (y.yr - 2020) * 0.20 + q.q * 0.03 + r.mult * 0.1))::int) * p.unit_cost,
    ROUND(((p.list_price - p.unit_cost) / p.list_price)::numeric, 4)
FROM
    (VALUES ('GE-SOLAR-001','SolarMax 400W','Solar Panels',349.99,120.00,2000),
            ('GE-SOLAR-002','SolarMax 600W','Solar Panels',499.99,180.00,1000),
            ('GE-WIND-001','WindTurbo 5kW','Wind Turbines',7999.99,2500.00,50),
            ('GE-BATT-001','PowerVault 10kWh','Battery Storage',5499.99,1800.00,200),
            ('GE-BATT-002','PowerVault 20kWh','Battery Storage',9999.99,3200.00,80),
            ('GE-MGMT-001','GridManager Pro','Energy Management',79.99,15.00,5000))
        AS p(product_id, product_name, category, list_price, unit_cost, base_qty),
    (VALUES (1),(2),(3),(4)) AS q(q),
    (VALUES (2020),(2021),(2022),(2023)) AS y(yr),
    (VALUES ('North America','United States',1.0),
            ('Europe','Germany',0.8),
            ('Asia Pacific','Australia',0.6),
            ('Middle East','UAE',0.4))
        AS r(region, country, mult);

-- Sales for HealthPlus
INSERT INTO sales_data (tenant_id, company_id, product_id, product_name, category, region, country, quarter, fiscal_year, quantity, unit_price, amount, discount, cost, gross_margin)
SELECT
    'benchmark', 'healthplus', p.product_id, p.product_name, p.category,
    r.region, r.country,
    'Q' || q.q, y.yr,
    (base_qty * (1 + (y.yr - 2020) * 0.30 + q.q * 0.04 + r.mult * 0.1))::int as quantity,
    p.list_price * (1 - 0.04 * r.mult),
    ((base_qty * (1 + (y.yr - 2020) * 0.30 + q.q * 0.04 + r.mult * 0.1))::int) * p.list_price * (1 - 0.04 * r.mult),
    ((base_qty * (1 + (y.yr - 2020) * 0.30 + q.q * 0.04 + r.mult * 0.1))::int) * p.list_price * 0.04 * r.mult,
    ((base_qty * (1 + (y.yr - 2020) * 0.30 + q.q * 0.04 + r.mult * 0.1))::int) * p.unit_cost,
    ROUND(((p.list_price - p.unit_cost) / p.list_price)::numeric, 4)
FROM
    (VALUES ('HP-DX-001','GenomeScan 1.0','Diagnostics',899.99,200.00,300),
            ('HP-DX-002','GenomeScan 2.0','Diagnostics',749.99,150.00,500),
            ('HP-TX-001','ImmunoBoost','Therapeutics',299.99,45.00,2000),
            ('HP-TX-002','NeuroShield','Therapeutics',499.99,80.00,800),
            ('HP-DG-001','MedAssist AI','Digital Health',59.99,10.00,6000),
            ('HP-DG-002','PatientHub','Digital Health',29.99,5.00,10000))
        AS p(product_id, product_name, category, list_price, unit_cost, base_qty),
    (VALUES (1),(2),(3),(4)) AS q(q),
    (VALUES (2020),(2021),(2022),(2023)) AS y(yr),
    (VALUES ('North America','United States',1.0),
            ('Europe','United Kingdom',0.7),
            ('Asia Pacific','China',0.5),
            ('Latin America','Mexico',0.2))
        AS r(region, country, mult);

-- === EMPLOYEES (50 per company) ===

INSERT INTO employees (tenant_id, company_id, employee_id, name, department, title, hire_date, salary, bonus, stock_options, region, status)
SELECT
    'benchmark', co.cid,
    co.cid || '-EMP-' || LPAD(s.n::text, 3, '0'),
    (ARRAY['James Chen','Sarah Johnson','Michael Brown','Emily Davis','David Wilson',
           'Maria Garcia','Robert Lee','Jennifer Taylor','William Anderson','Lisa Thomas',
           'Daniel Martinez','Amanda White','Christopher Harris','Jessica Clark','Matthew Lewis',
           'Ashley Robinson','Joshua Walker','Stephanie Hall','Andrew Allen','Nicole Young',
           'Ryan King','Megan Wright','Brandon Scott','Rachel Green','Kevin Adams',
           'Lauren Nelson','Justin Baker','Samantha Hill','Tyler Rivera','Hannah Campbell',
           'Nathan Mitchell','Kayla Roberts','Jacob Carter','Olivia Phillips','Zachary Evans',
           'Abigail Turner','Ethan Collins','Madison Stewart','Dylan Morris','Victoria Murphy',
           'Aaron Cook','Brittany Rogers','Luke Reed','Morgan Bailey','Caleb Cooper',
           'Paige Richardson','Owen Cox','Sierra Howard','Ian Ward','Haley Brooks'])[s.n],
    (ARRAY['Engineering','Engineering','Engineering','Engineering','Sales',
           'Sales','Marketing','Marketing','Finance','Finance',
           'Operations','Operations','HR','Product','Product',
           'Research','Research','Engineering','Engineering','Sales',
           'Sales','Marketing','Finance','Operations','HR',
           'Product','Research','Engineering','Engineering','Sales',
           'Marketing','Finance','Operations','HR','Product',
           'Research','Engineering','Sales','Marketing','Finance',
           'Operations','HR','Product','Research','Engineering',
           'Sales','Marketing','Finance','Operations','HR'])[s.n],
    (ARRAY['Software Engineer','Senior Engineer','Tech Lead','Staff Engineer','Account Executive',
           'Sales Director','Marketing Manager','Content Strategist','Financial Analyst','Controller',
           'Operations Manager','Logistics Coordinator','HR Business Partner','Product Manager','UX Designer',
           'Research Scientist','Lab Director','DevOps Engineer','Frontend Developer','Sales Representative',
           'Enterprise Sales','Digital Marketing Lead','Senior Analyst','Supply Chain Manager','Recruiter',
           'Senior PM','Research Associate','Backend Developer','QA Engineer','Account Manager',
           'Brand Manager','Treasury Analyst','Facilities Manager','HR Director','VP Product',
           'Principal Scientist','Solutions Architect','Regional Sales Mgr','Creative Director','CFO Office',
           'COO Office','VP People','VP Product Strategy','CTO Office','Distinguished Engineer',
           'VP Sales','CMO Office','VP Finance','VP Operations','CHRO'])[s.n],
    ('2018-01-01'::date + ((s.n * 37 + co.off) % 2000)),
    (ARRAY[145000,185000,210000,230000,95000,160000,120000,90000,110000,155000,
           125000,75000,105000,150000,115000,165000,195000,140000,130000,85000,
           170000,110000,125000,135000,95000,160000,120000,150000,105000,100000,
           115000,120000,85000,155000,200000,190000,175000,145000,130000,180000,
           160000,155000,195000,220000,250000,180000,170000,165000,150000,145000])[s.n],
    (ARRAY[145000,185000,210000,230000,95000,160000,120000,90000,110000,155000,
           125000,75000,105000,150000,115000,165000,195000,140000,130000,85000,
           170000,110000,125000,135000,95000,160000,120000,150000,105000,100000,
           115000,120000,85000,155000,200000,190000,175000,145000,130000,180000,
           160000,155000,195000,220000,250000,180000,170000,165000,150000,145000])[s.n] * 0.1,
    (s.n * 100 + co.off) % 2000,
    (ARRAY['North America','North America','North America','Europe','Europe',
           'Europe','Asia Pacific','Asia Pacific','Asia Pacific','Latin America',
           'North America','North America','North America','Europe','Europe',
           'Asia Pacific','Asia Pacific','North America','North America','Europe',
           'Europe','Asia Pacific','North America','North America','Europe',
           'Asia Pacific','North America','North America','Europe','Europe',
           'Asia Pacific','North America','North America','Europe','North America',
           'Asia Pacific','North America','Europe','North America','North America',
           'Europe','North America','Asia Pacific','North America','North America',
           'Europe','North America','North America','Europe','North America'])[s.n],
    CASE WHEN s.n <= 47 THEN 'active' ELSE 'inactive' END
FROM
    (VALUES ('techvision', 0), ('greenenergy', 100), ('healthplus', 200)) AS co(cid, off),
    generate_series(1, 50) AS s(n)
ON CONFLICT (tenant_id, company_id, employee_id) DO NOTHING;

-- ============================================================
-- Verify counts
-- ============================================================
SELECT 'financials' as tbl, COUNT(*) as rows FROM financials WHERE tenant_id = 'benchmark'
UNION ALL
SELECT 'balance_sheet', COUNT(*) FROM balance_sheet WHERE tenant_id = 'benchmark'
UNION ALL
SELECT 'products', COUNT(*) FROM products WHERE tenant_id = 'benchmark'
UNION ALL
SELECT 'sales_data', COUNT(*) FROM sales_data WHERE tenant_id = 'benchmark'
UNION ALL
SELECT 'employees', COUNT(*) FROM employees WHERE tenant_id = 'benchmark'
ORDER BY tbl;
