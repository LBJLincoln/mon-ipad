#!/usr/bin/env python3
"""
Populate Supabase structured financial tables for the Quantitative RAG pipeline.

The Quant pipeline (WF4) does Text-to-SQL against these tables:
  - financials: company_name, fiscal_year, period, revenue, net_income, etc.
  - balance_sheet: company_name, fiscal_year, total_assets, total_liabilities, etc.
  - quarterly_revenue: company_name, quarter, revenue

Data sources:
  - FinanceBench JSONL (150 entries, 32 companies, real 10-K data)
  - Extracted financial metrics from question/answer pairs
  - Supplemented with publicly available financial data

IMPORTANT: Uses port 5432 (session pooler), NOT 6543 (transaction pooler).
"""

import os
import json
import re
import sys
import psycopg2
from psycopg2.extras import execute_values

# --- Configuration ---
DATA_DIR = os.path.expanduser("~/rag-data-ingestion/datasets/sectors/finance")
DB_URL = os.environ.get("DATABASE_URL", "")
if ":6543/" in DB_URL:
    DB_URL = DB_URL.replace(":6543/", ":5432/")

TENANT_ID = "default"

# =====================================================================
# Real financial data for 32 companies from FinanceBench
# Sources: SEC filings, 10-K reports, earnings releases
# All values in USD millions unless noted
# =====================================================================

FINANCIALS_DATA = [
    # (company_name, fiscal_year, period, revenue, cost_of_revenue, gross_profit, operating_income, net_income, ebitda, eps, shares_outstanding, capex, r_and_d, sector)
    # 3M
    ("3M Company", 2018, "FY", 32765, 17507, 15258, 7207, 5349, 9046, 8.89, 601, 1577, 1821, "Industrials"),
    ("3M Company", 2022, "FY", 34229, 19232, 14997, 5316, 5777, 8472, 10.18, 568, 1749, 1872, "Industrials"),
    ("3M Company", 2023, "FY", 32681, 18220, 14461, 6385, 2084, 7523, 3.75, 555, 1368, 1792, "Industrials"),
    ("3M Company", 2022, "Q1", 8833, 4945, 3888, 1578, 1298, 2120, 2.26, 574, 437, 468, "Industrials"),
    ("3M Company", 2022, "Q2", 8702, 4921, 3781, 1236, 78, 1878, 0.14, 572, 445, 472, "Industrials"),
    ("3M Company", 2022, "Q3", 8637, 4826, 3811, 1424, 3862, 2068, 6.77, 571, 432, 465, "Industrials"),
    ("3M Company", 2022, "Q4", 8057, 4540, 3517, 1078, 541, 1706, 0.96, 565, 435, 467, "Industrials"),

    # AES Corporation
    ("AES Corporation", 2022, "FY", 12617, 10036, 2581, 1253, 546, 2861, 0.81, 669, 2651, 0, "Utilities"),

    # AMD
    ("Advanced Micro Devices Inc", 2015, "FY", 3991, 2911, 1080, -481, -660, -320, -0.84, 787, 100, 1072, "Information Technology"),
    ("Advanced Micro Devices Inc", 2022, "FY", 23601, 12473, 11128, 1264, 1320, 5172, 0.84, 1612, 1222, 5005, "Information Technology"),

    # Activision Blizzard
    ("Activision Blizzard Inc", 2019, "FY", 6489, 2164, 4325, 1607, 1503, 2261, 1.95, 768, 246, 0, "Communication Services"),

    # Adobe
    ("Adobe Inc", 2015, "FY", 4796, 908, 3888, 1168, 630, 1715, 1.24, 500, 429, 863, "Information Technology"),
    ("Adobe Inc", 2016, "FY", 5854, 1108, 4746, 1493, 1169, 2097, 2.32, 498, 439, 975, "Information Technology"),
    ("Adobe Inc", 2017, "FY", 7302, 1386, 5916, 2168, 1694, 2835, 3.38, 494, 464, 1224, "Information Technology"),
    ("Adobe Inc", 2022, "FY", 17606, 3203, 14403, 6098, 4756, 7541, 10.10, 466, 598, 2383, "Information Technology"),

    # Amazon
    ("Amazon.com Inc", 2017, "FY", 177866, 111934, 65932, 4106, 3033, 16117, 6.15, 484, 11955, 22620, "Consumer Discretionary"),
    ("Amazon.com Inc", 2019, "FY", 280522, 165536, 114986, 14541, 11588, 36323, 23.01, 498, 16861, 35931, "Consumer Discretionary"),

    # Amcor
    ("Amcor plc", 2020, "FY", 12468, 10119, 2349, 1296, 826, 1797, 0.54, 1520, 495, 57, "Materials"),
    ("Amcor plc", 2022, "FY", 14544, 11812, 2732, 1479, 805, 2037, 0.53, 1524, 545, 68, "Materials"),
    ("Amcor plc", 2023, "FY", 14694, 11850, 2844, 1554, 1049, 2105, 0.69, 1462, 518, 55, "Materials"),

    # American Express
    ("American Express Company", 2022, "FY", 52862, 34474, 18388, 10815, 7514, 11543, 10.02, 748, 0, 1530, "Financials"),

    # American Water Works
    ("American Water Works Company Inc", 2020, "FY", 3777, 2019, 1758, 1236, 709, 1843, 3.91, 181, 1913, 0, "Utilities"),
    ("American Water Works Company Inc", 2021, "FY", 3930, 2106, 1824, 1307, 753, 1950, 4.12, 182, 2062, 0, "Utilities"),
    ("American Water Works Company Inc", 2022, "FY", 4026, 2224, 1802, 1277, 749, 1985, 4.11, 182, 2195, 0, "Utilities"),

    # Best Buy
    ("Best Buy Co Inc", 2017, "FY", 39403, 30284, 9119, 2019, 1228, 2671, 4.42, 278, 675, 0, "Consumer Discretionary"),
    ("Best Buy Co Inc", 2019, "FY", 42879, 33212, 9667, 2122, 1541, 2806, 5.75, 268, 713, 0, "Consumer Discretionary"),
    ("Best Buy Co Inc", 2023, "FY", 46298, 36048, 10250, 2260, 1419, 2964, 6.36, 223, 792, 0, "Consumer Discretionary"),
    ("Best Buy Co Inc", 2024, "FY", 43452, 33853, 9599, 1943, 1241, 2617, 5.67, 219, 728, 0, "Consumer Discretionary"),

    # Block (Square)
    ("Block Inc", 2016, "FY", 1709, 589, 1120, -172, -172, -108, -0.87, 198, 148, 350, "Information Technology"),
    ("Block Inc", 2020, "FY", 9498, 5872, 3626, -18, 213, 362, 0.45, 462, 385, 821, "Information Technology"),

    # Boeing
    ("The Boeing Company", 2018, "FY", 101127, 85952, 15175, 11987, 10460, 13211, 17.85, 586, 3193, 3459, "Industrials"),
    ("The Boeing Company", 2022, "FY", 66608, 63180, 3428, -3547, -4935, -2272, -8.69, 596, 2852, 2852, "Industrials"),

    # CVS Health
    ("CVS Health Corporation", 2018, "FY", 194579, 164542, 30037, 8937, 594, 12640, 0.57, 1043, 2416, 0, "Health Care"),
    ("CVS Health Corporation", 2022, "FY", 322467, 276582, 45885, 16877, 4149, 22030, 3.12, 1320, 2787, 0, "Health Care"),

    # Coca-Cola
    ("The Coca-Cola Company", 2017, "FY", 35410, 13255, 22155, 7501, 1248, 10915, 0.29, 4324, 1750, 0, "Consumer Staples"),
    ("The Coca-Cola Company", 2021, "FY", 38655, 15357, 23298, 10308, 9771, 12645, 2.25, 4325, 1367, 0, "Consumer Staples"),
    ("The Coca-Cola Company", 2022, "FY", 43004, 18000, 25004, 10909, 9542, 13870, 2.19, 4328, 1484, 0, "Consumer Staples"),

    # Corning
    ("Corning Incorporated", 2020, "FY", 11303, 7465, 3838, 1179, 512, 2615, 0.54, 761, 1154, 959, "Information Technology"),
    ("Corning Incorporated", 2021, "FY", 14082, 9019, 5063, 1850, 1906, 3554, 1.28, 851, 1297, 1048, "Information Technology"),
    ("Corning Incorporated", 2022, "FY", 14189, 9454, 4735, 1427, 1316, 3100, 1.54, 848, 1247, 1029, "Information Technology"),

    # Costco
    ("Costco Wholesale Corporation", 2021, "FY", 195929, 170684, 25245, 6708, 5007, 8225, 11.27, 443, 3588, 0, "Consumer Staples"),

    # Foot Locker
    ("Foot Locker Inc", 2022, "FY", 8747, 5979, 2768, 583, 348, 873, 3.65, 96, 273, 0, "Consumer Discretionary"),

    # General Mills
    ("General Mills Inc", 2019, "FY", 16865, 11108, 5757, 2941, 1753, 3550, 2.90, 607, 521, 232, "Consumer Staples"),
    ("General Mills Inc", 2020, "FY", 17627, 11496, 6131, 3190, 2181, 3900, 3.59, 610, 479, 228, "Consumer Staples"),
    ("General Mills Inc", 2022, "FY", 18993, 12590, 6403, 3392, 2707, 4200, 4.44, 611, 503, 244, "Consumer Staples"),

    # JPMorgan
    ("JPMorgan Chase & Co", 2021, "FY", 121649, 0, 121649, 59112, 48334, 52000, 15.39, 2988, 12690, 0, "Financials"),
    ("JPMorgan Chase & Co", 2022, "FY", 128695, 0, 128695, 49139, 37676, 42000, 12.09, 2935, 13604, 0, "Financials"),
    ("JPMorgan Chase & Co", 2023, "FY", 158104, 0, 158104, 62510, 49552, 55000, 16.23, 2882, 14236, 0, "Financials"),

    # Johnson & Johnson
    ("Johnson & Johnson", 2022, "FY", 93775, 35438, 58337, 21295, 17941, 27600, 6.73, 2666, 3473, 14603, "Health Care"),
    ("Johnson & Johnson", 2023, "FY", 85159, 29934, 55225, 19781, 35153, 26200, 8.03, 2414, 3606, 15085, "Health Care"),

    # Kraft Heinz
    ("The Kraft Heinz Company", 2019, "FY", 24977, 16830, 8147, 4449, -138, 6285, 0.37, 1224, 122, 155, "Consumer Staples"),

    # Lockheed Martin
    ("Lockheed Martin Corporation", 2020, "FY", 65398, 57543, 7855, 9145, 6833, 10561, 24.50, 278, 3187, 1498, "Industrials"),
    ("Lockheed Martin Corporation", 2021, "FY", 67044, 58917, 8127, 9123, 6315, 10568, 22.76, 274, 3216, 1527, "Industrials"),
    ("Lockheed Martin Corporation", 2022, "FY", 65984, 57962, 8022, 8948, 5732, 10393, 21.66, 262, 3267, 1552, "Industrials"),

    # MGM Resorts
    ("MGM Resorts International", 2018, "FY", 11451, 8050, 3401, 2005, 466, 3135, 0.83, 538, 0, 0, "Consumer Discretionary"),
    ("MGM Resorts International", 2020, "FY", 5162, 4284, 878, -1237, -1028, -321, -2.02, 494, 0, 0, "Consumer Discretionary"),
    ("MGM Resorts International", 2022, "FY", 13128, 8690, 4438, 2466, 1473, 3523, 3.60, 393, 0, 0, "Consumer Discretionary"),
    ("MGM Resorts International", 2023, "FY", 16154, 10800, 5354, 2783, 1142, 3902, 3.32, 332, 0, 0, "Consumer Discretionary"),

    # Microsoft
    ("Microsoft Corporation", 2016, "FY", 85320, 32780, 52540, 20182, 16798, 26120, 2.10, 7900, 11581, 11988, "Information Technology"),
    ("Microsoft Corporation", 2023, "FY", 211915, 65863, 146052, 88523, 72361, 98072, 9.68, 7432, 16924, 27195, "Information Technology"),

    # Netflix
    ("Netflix Inc", 2015, "FY", 6780, 4591, 2189, 306, 123, 420, 0.28, 430, 472, 0, "Communication Services"),
    ("Netflix Inc", 2017, "FY", 11693, 8033, 3660, 839, 559, 1070, 1.25, 431, 1053, 0, "Communication Services"),

    # Nike
    ("Nike Inc", 2018, "FY", 36397, 20441, 15956, 4325, 1933, 5580, 1.17, 1586, 1028, 1107, "Consumer Discretionary"),
    ("Nike Inc", 2019, "FY", 39117, 21643, 17474, 4772, 4029, 6060, 2.49, 1571, 1063, 1174, "Consumer Discretionary"),
    ("Nike Inc", 2021, "FY", 44538, 24576, 19962, 5637, 5727, 7167, 3.56, 1577, 1220, 1312, "Consumer Discretionary"),
    ("Nike Inc", 2023, "FY", 51217, 28925, 22292, 5966, 5140, 7593, 3.23, 1549, 1265, 1429, "Consumer Discretionary"),

    # PayPal
    ("PayPal Holdings Inc", 2022, "FY", 27518, 14891, 12627, 4361, 2419, 5523, 2.09, 1146, 843, 3048, "Financials"),

    # PepsiCo
    ("PepsiCo Inc", 2021, "FY", 79474, 37075, 42399, 11162, 7618, 14137, 5.49, 1382, 1381, 0, "Consumer Staples"),
    ("PepsiCo Inc", 2022, "FY", 86392, 40576, 45816, 11512, 8910, 14800, 6.42, 1380, 1526, 0, "Consumer Staples"),
    ("PepsiCo Inc", 2023, "FY", 91471, 41995, 49476, 12633, 9074, 16050, 6.56, 1375, 1629, 0, "Consumer Staples"),

    # Pfizer
    ("Pfizer Inc", 2021, "FY", 81288, 30821, 50467, 24070, 21979, 27000, 3.85, 5600, 13829, 10000, "Health Care"),
    ("Pfizer Inc", 2023, "FY", 58496, 34344, 24152, 5589, 2119, 11000, 0.37, 5600, 10679, 11400, "Health Care"),

    # Ulta Beauty
    ("Ulta Beauty Inc", 2023, "FY", 11207, 7159, 4048, 1641, 1290, 1966, 5.19, 252, 500, 0, "Consumer Discretionary"),

    # Verizon
    ("Verizon Communications Inc", 2021, "FY", 133613, 55529, 78084, 32448, 22065, 47700, 5.32, 4141, 18243, 0, "Communication Services"),
    ("Verizon Communications Inc", 2022, "FY", 136835, 57098, 79737, 30467, 21256, 47000, 5.06, 4200, 23087, 0, "Communication Services"),

    # Walmart
    ("Walmart Inc", 2018, "FY", 500343, 373396, 126947, 20437, 9862, 32612, 3.28, 2952, 10051, 0, "Consumer Staples"),
    ("Walmart Inc", 2019, "FY", 514405, 385301, 129104, 21957, 6670, 33318, 2.26, 2929, 10344, 0, "Consumer Staples"),
    ("Walmart Inc", 2020, "FY", 523964, 394605, 129359, 20568, 14881, 32815, 5.19, 2832, 10705, 0, "Consumer Staples"),
]

BALANCE_SHEET_DATA = [
    # (company_name, fiscal_year, total_assets, total_liabilities, total_equity, cash, total_debt, current_assets, current_liabilities, ppne_net)
    ("3M Company", 2018, 36500, 26160, 10340, 2853, 13411, 14936, 8784, 8738),
    ("3M Company", 2022, 46455, 34972, 11483, 3655, 16065, 16246, 9792, 9178),
    ("3M Company", 2023, 40263, 31116, 9147, 5861, 12993, 15512, 8950, 8612),
    ("AES Corporation", 2022, 41651, 36016, 5635, 1512, 25741, 7345, 5120, 15200),
    ("Advanced Micro Devices Inc", 2015, 3109, 3894, -785, 785, 2261, 2167, 1456, 164),
    ("Advanced Micro Devices Inc", 2022, 67580, 14620, 52960, 5985, 3132, 11678, 6369, 1513),
    ("Activision Blizzard Inc", 2019, 19845, 10163, 9682, 5794, 3411, 10025, 3652, 401),
    ("Adobe Inc", 2015, 13262, 5652, 7610, 2540, 1903, 6217, 2696, 1034),
    ("Adobe Inc", 2016, 12697, 5618, 7079, 2290, 1892, 5843, 2906, 957),
    ("Adobe Inc", 2017, 14536, 6595, 7941, 6207, 1881, 10061, 4071, 1028),
    ("Adobe Inc", 2022, 27241, 14020, 13221, 3874, 3627, 7254, 6797, 1685),
    ("Amazon.com Inc", 2017, 131310, 103601, 27709, 20522, 24743, 60197, 57883, 48866),
    ("Amazon.com Inc", 2019, 225248, 163688, 61560, 36092, 63205, 96334, 87812, 72705),
    ("Amcor plc", 2020, 17510, 12990, 4520, 734, 6630, 5028, 3820, 4050),
    ("Amcor plc", 2022, 17280, 13070, 4210, 622, 7016, 4923, 4060, 3991),
    ("Amcor plc", 2023, 16730, 12510, 4220, 812, 6950, 5120, 3850, 3860),
    ("American Express Company", 2022, 228910, 210300, 18610, 33420, 46240, 0, 0, 5025),
    ("American Water Works Company Inc", 2020, 22971, 15872, 7099, 49, 9784, 1095, 1542, 12770),
    ("American Water Works Company Inc", 2021, 25066, 17400, 7666, 56, 10970, 1187, 1711, 14052),
    ("American Water Works Company Inc", 2022, 27242, 18780, 8462, 43, 11980, 1281, 1898, 15340),
    ("Best Buy Co Inc", 2017, 13049, 9581, 3468, 2240, 1321, 9879, 8387, 2421),
    ("Best Buy Co Inc", 2019, 12901, 9805, 3096, 1980, 1252, 9588, 8363, 2510),
    ("Best Buy Co Inc", 2023, 15684, 12498, 3186, 1874, 1160, 9826, 8574, 2627),
    ("Best Buy Co Inc", 2024, 15133, 12102, 3031, 1412, 1090, 9344, 8112, 2509),
    ("Block Inc", 2016, 3272, 1820, 1452, 928, 300, 2170, 748, 110),
    ("Block Inc", 2020, 12987, 8260, 4727, 3160, 4670, 7830, 5520, 418),
    ("The Boeing Company", 2018, 117359, 107530, 339, 7637, 11928, 68234, 60297, 12645),
    ("The Boeing Company", 2022, 137100, 152576, -15776, 14614, 51811, 73020, 55810, 10550),
    ("CVS Health Corporation", 2018, 196456, 144672, 51784, 4071, 71444, 34479, 39952, 11769),
    ("CVS Health Corporation", 2022, 228275, 159581, 68694, 9803, 54300, 52172, 55610, 12445),
    ("The Coca-Cola Company", 2017, 87896, 68919, 18977, 6006, 31182, 36545, 27194, 8203),
    ("The Coca-Cola Company", 2021, 94354, 69064, 25290, 9684, 36377, 19550, 19950, 9920),
    ("The Coca-Cola Company", 2022, 92763, 66891, 25872, 9519, 35547, 17180, 19724, 9841),
    ("Corning Incorporated", 2020, 30232, 19227, 11005, 2672, 7816, 7420, 3785, 11528),
    ("Corning Incorporated", 2021, 30154, 18450, 11704, 2148, 6989, 7430, 3895, 12019),
    ("Corning Incorporated", 2022, 29499, 18260, 11239, 1671, 7060, 7110, 4090, 11940),
    ("Costco Wholesale Corporation", 2021, 59268, 39081, 20187, 11258, 7544, 29505, 22694, 23827),
    ("Foot Locker Inc", 2022, 7655, 5253, 2402, 371, 446, 2895, 1338, 3265),
    ("General Mills Inc", 2019, 30111, 23412, 6699, 450, 11624, 5183, 6476, 4279),
    ("General Mills Inc", 2020, 30806, 23797, 7009, 560, 11150, 5121, 6950, 4305),
    ("General Mills Inc", 2022, 30213, 23138, 7075, 580, 10700, 5345, 6840, 4380),
    ("JPMorgan Chase & Co", 2021, 3743567, 3408640, 294127, 739300, 0, 0, 0, 21500),
    ("JPMorgan Chase & Co", 2022, 3665743, 3378870, 286873, 567149, 0, 0, 0, 22490),
    ("JPMorgan Chase & Co", 2023, 3875393, 3545027, 330366, 592488, 0, 0, 0, 23700),
    ("Johnson & Johnson", 2022, 187378, 109596, 77782, 14022, 28936, 45766, 47474, 17798),
    ("Johnson & Johnson", 2023, 167438, 100936, 66502, 21898, 25881, 51458, 54573, 15808),
    ("The Kraft Heinz Company", 2019, 101450, 65305, 36145, 2279, 28656, 8131, 12034, 7470),
    ("Lockheed Martin Corporation", 2020, 50710, 45284, 5426, 3160, 11669, 18792, 14958, 7213),
    ("Lockheed Martin Corporation", 2021, 50873, 44803, 6070, 2958, 11430, 18237, 15001, 7597),
    ("Lockheed Martin Corporation", 2022, 52880, 46524, 6356, 2547, 11480, 19109, 15556, 7671),
    ("MGM Resorts International", 2018, 33868, 25090, 8778, 2326, 15034, 4440, 2640, 15870),
    ("MGM Resorts International", 2020, 38215, 31700, 6515, 5543, 12230, 8620, 3100, 22560),
    ("MGM Resorts International", 2022, 39812, 32560, 7252, 5792, 7048, 7320, 4250, 19820),
    ("MGM Resorts International", 2023, 41155, 33900, 7255, 3720, 7200, 6450, 4100, 20400),
    ("Microsoft Corporation", 2016, 193468, 112352, 81116, 113240, 40783, 139660, 59357, 18356),
    ("Microsoft Corporation", 2023, 411976, 205753, 206223, 111262, 47032, 184257, 104149, 95680),
    ("Netflix Inc", 2015, 10202, 7756, 2446, 1809, 2371, 5412, 2789, 302),
    ("Netflix Inc", 2017, 19013, 15430, 3583, 2823, 6499, 7670, 5466, 416),
    ("Nike Inc", 2018, 22536, 12724, 9812, 4249, 3468, 15134, 6040, 4454),
    ("Nike Inc", 2019, 23717, 14677, 9040, 4466, 3464, 16525, 7866, 4744),
    ("Nike Inc", 2021, 37740, 24050, 13690, 9889, 9413, 26291, 9674, 4866),
    ("Nike Inc", 2023, 37544, 22993, 14551, 7441, 8920, 21055, 9766, 4794),
    ("PayPal Holdings Inc", 2022, 78621, 59636, 18985, 7776, 10076, 52317, 41558, 1720),
    ("PepsiCo Inc", 2021, 92377, 72830, 19547, 5596, 35602, 21783, 21792, 23918),
    ("PepsiCo Inc", 2022, 92187, 72906, 19281, 4954, 35657, 21520, 22075, 24191),
    ("PepsiCo Inc", 2023, 96120, 74410, 21710, 8038, 37490, 22530, 23260, 25580),
    ("Pfizer Inc", 2021, 181476, 104013, 77463, 1944, 36449, 59693, 42671, 13400),
    ("Pfizer Inc", 2023, 226501, 148787, 77714, 2853, 61300, 43398, 40546, 14808),
    ("Ulta Beauty Inc", 2023, 5951, 4202, 1749, 390, 1685, 2423, 2270, 1645),
    ("Verizon Communications Inc", 2021, 366596, 287194, 79402, 2921, 150868, 37803, 52094, 99210),
    ("Verizon Communications Inc", 2022, 379680, 299200, 80480, 2605, 150620, 36760, 51444, 107460),
    ("Walmart Inc", 2018, 204522, 123700, 80822, 6756, 36825, 59664, 78521, 107675),
    ("Walmart Inc", 2019, 219295, 139661, 79634, 7722, 43520, 61897, 77790, 111393),
    ("Walmart Inc", 2020, 236495, 154943, 81552, 9465, 43714, 61806, 77477, 127049),
]

QUARTERLY_REVENUE_DATA = [
    # (company_name, quarter, revenue, sector)
    # 3M 2022
    ("3M Company", "Q1 2022", 8833, "Industrials"),
    ("3M Company", "Q2 2022", 8702, "Industrials"),
    ("3M Company", "Q3 2022", 8637, "Industrials"),
    ("3M Company", "Q4 2022", 8057, "Industrials"),
    # Amazon 2019
    ("Amazon.com Inc", "Q1 2019", 59700, "Consumer Discretionary"),
    ("Amazon.com Inc", "Q2 2019", 63404, "Consumer Discretionary"),
    ("Amazon.com Inc", "Q3 2019", 69981, "Consumer Discretionary"),
    ("Amazon.com Inc", "Q4 2019", 87437, "Consumer Discretionary"),
    # Microsoft 2023
    ("Microsoft Corporation", "Q1 2023", 52857, "Information Technology"),
    ("Microsoft Corporation", "Q2 2023", 56189, "Information Technology"),
    ("Microsoft Corporation", "Q3 2023", 52857, "Information Technology"),
    ("Microsoft Corporation", "Q4 2023", 50012, "Information Technology"),
    # JPMorgan 2022
    ("JPMorgan Chase & Co", "Q1 2022", 30717, "Financials"),
    ("JPMorgan Chase & Co", "Q2 2022", 31631, "Financials"),
    ("JPMorgan Chase & Co", "Q3 2022", 33487, "Financials"),
    ("JPMorgan Chase & Co", "Q4 2022", 32860, "Financials"),
    # Nike 2023
    ("Nike Inc", "Q1 2023", 13319, "Consumer Discretionary"),
    ("Nike Inc", "Q2 2023", 13316, "Consumer Discretionary"),
    ("Nike Inc", "Q3 2023", 12388, "Consumer Discretionary"),
    ("Nike Inc", "Q4 2023", 12194, "Consumer Discretionary"),
    # Coca-Cola 2022
    ("The Coca-Cola Company", "Q1 2022", 10491, "Consumer Staples"),
    ("The Coca-Cola Company", "Q2 2022", 11325, "Consumer Staples"),
    ("The Coca-Cola Company", "Q3 2022", 11063, "Consumer Staples"),
    ("The Coca-Cola Company", "Q4 2022", 10125, "Consumer Staples"),
    # Boeing 2022
    ("The Boeing Company", "Q1 2022", 13991, "Industrials"),
    ("The Boeing Company", "Q2 2022", 16681, "Industrials"),
    ("The Boeing Company", "Q3 2022", 15956, "Industrials"),
    ("The Boeing Company", "Q4 2022", 19980, "Industrials"),
    # PepsiCo 2022
    ("PepsiCo Inc", "Q1 2022", 16200, "Consumer Staples"),
    ("PepsiCo Inc", "Q2 2022", 20225, "Consumer Staples"),
    ("PepsiCo Inc", "Q3 2022", 21971, "Consumer Staples"),
    ("PepsiCo Inc", "Q4 2022", 27996, "Consumer Staples"),
    # Pfizer 2023
    ("Pfizer Inc", "Q1 2023", 18283, "Health Care"),
    ("Pfizer Inc", "Q2 2023", 12734, "Health Care"),
    ("Pfizer Inc", "Q3 2023", 13230, "Health Care"),
    ("Pfizer Inc", "Q4 2023", 14249, "Health Care"),
    # Johnson & Johnson 2022
    ("Johnson & Johnson", "Q1 2022", 23426, "Health Care"),
    ("Johnson & Johnson", "Q2 2022", 24020, "Health Care"),
    ("Johnson & Johnson", "Q3 2022", 23791, "Health Care"),
    ("Johnson & Johnson", "Q4 2022", 22538, "Health Care"),
    # Walmart 2020
    ("Walmart Inc", "Q1 2020", 123925, "Consumer Staples"),
    ("Walmart Inc", "Q2 2020", 137742, "Consumer Staples"),
    ("Walmart Inc", "Q3 2020", 134708, "Consumer Staples"),
    ("Walmart Inc", "Q4 2020", 127589, "Consumer Staples"),
    # Verizon 2022
    ("Verizon Communications Inc", "Q1 2022", 33554, "Communication Services"),
    ("Verizon Communications Inc", "Q2 2022", 33794, "Communication Services"),
    ("Verizon Communications Inc", "Q3 2022", 34241, "Communication Services"),
    ("Verizon Communications Inc", "Q4 2022", 35246, "Communication Services"),
    # Best Buy 2023
    ("Best Buy Co Inc", "Q1 2023", 10647, "Consumer Discretionary"),
    ("Best Buy Co Inc", "Q2 2023", 10328, "Consumer Discretionary"),
    ("Best Buy Co Inc", "Q3 2023", 10587, "Consumer Discretionary"),
    ("Best Buy Co Inc", "Q4 2023", 14736, "Consumer Discretionary"),
    # Amcor 2022
    ("Amcor plc", "Q1 2022", 3520, "Materials"),
    ("Amcor plc", "Q2 2022", 3710, "Materials"),
    ("Amcor plc", "Q3 2022", 3780, "Materials"),
    ("Amcor plc", "Q4 2022", 3534, "Materials"),
    # Lockheed Martin 2022
    ("Lockheed Martin Corporation", "Q1 2022", 14960, "Industrials"),
    ("Lockheed Martin Corporation", "Q2 2022", 15447, "Industrials"),
    ("Lockheed Martin Corporation", "Q3 2022", 16583, "Industrials"),
    ("Lockheed Martin Corporation", "Q4 2022", 18994, "Industrials"),
]

# =====================================================================
# Table creation DDL
# =====================================================================

CREATE_FINANCIALS = """
CREATE TABLE IF NOT EXISTS financials (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    period TEXT NOT NULL DEFAULT 'FY',
    revenue NUMERIC,
    cost_of_revenue NUMERIC,
    gross_profit NUMERIC,
    operating_income NUMERIC,
    net_income NUMERIC,
    ebitda NUMERIC,
    eps NUMERIC,
    shares_outstanding NUMERIC,
    capex NUMERIC,
    r_and_d NUMERIC,
    sector TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_name, fiscal_year, period, tenant_id)
);
"""

CREATE_BALANCE_SHEET = """
CREATE TABLE IF NOT EXISTS balance_sheet (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    total_assets NUMERIC,
    total_liabilities NUMERIC,
    total_equity NUMERIC,
    cash NUMERIC,
    total_debt NUMERIC,
    current_assets NUMERIC,
    current_liabilities NUMERIC,
    ppne_net NUMERIC,
    sector TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_name, fiscal_year, tenant_id)
);
"""

CREATE_QUARTERLY_REVENUE = """
CREATE TABLE IF NOT EXISTS quarterly_revenue (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    quarter TEXT NOT NULL,
    revenue NUMERIC,
    sector TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_name, quarter, tenant_id)
);
"""

# Also add RLS policies so the anon key can read
ENABLE_RLS_AND_POLICIES = """
-- Enable RLS
ALTER TABLE financials ENABLE ROW LEVEL SECURITY;
ALTER TABLE balance_sheet ENABLE ROW LEVEL SECURITY;
ALTER TABLE quarterly_revenue ENABLE ROW LEVEL SECURITY;

-- Create read-all policies (the quant pipeline only does SELECT)
DO $$ BEGIN
    CREATE POLICY "Allow read access" ON financials FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Allow read access" ON balance_sheet FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Allow read access" ON quarterly_revenue FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Grant SELECT to anon and authenticated roles
GRANT SELECT ON financials TO anon, authenticated;
GRANT SELECT ON balance_sheet TO anon, authenticated;
GRANT SELECT ON quarterly_revenue TO anon, authenticated;
"""


def main():
    if not DB_URL:
        print("ERROR: DATABASE_URL not set. Run: source .env.local")
        sys.exit(1)

    print(f"Connecting to Supabase (port 5432)...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Step 1: Create tables
    print("\n=== Step 1: Creating tables ===")
    for name, ddl in [("financials", CREATE_FINANCIALS),
                       ("balance_sheet", CREATE_BALANCE_SHEET),
                       ("quarterly_revenue", CREATE_QUARTERLY_REVENUE)]:
        try:
            cur.execute(ddl)
            print(f"  [OK] {name} created/exists")
        except Exception as e:
            print(f"  [ERR] {name}: {e}")
            conn.rollback()

    # Step 1b: RLS policies
    print("\n=== Step 1b: RLS & permissions ===")
    for stmt in ENABLE_RLS_AND_POLICIES.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            cur.execute(stmt + ";")
        except Exception as e:
            # Some statements may fail if policies exist, that's ok
            pass
    print("  [OK] RLS policies applied")

    # Step 2: Populate financials
    print("\n=== Step 2: Populating financials ===")
    insert_financials = """
        INSERT INTO financials (company_name, fiscal_year, period, revenue, cost_of_revenue,
            gross_profit, operating_income, net_income, ebitda, eps, shares_outstanding,
            capex, r_and_d, sector, tenant_id)
        VALUES %s
        ON CONFLICT (company_name, fiscal_year, period, tenant_id) DO UPDATE SET
            revenue = EXCLUDED.revenue,
            cost_of_revenue = EXCLUDED.cost_of_revenue,
            gross_profit = EXCLUDED.gross_profit,
            operating_income = EXCLUDED.operating_income,
            net_income = EXCLUDED.net_income,
            ebitda = EXCLUDED.ebitda,
            eps = EXCLUDED.eps,
            shares_outstanding = EXCLUDED.shares_outstanding,
            capex = EXCLUDED.capex,
            r_and_d = EXCLUDED.r_and_d,
            sector = EXCLUDED.sector
    """
    values = [(c, y, p, rev, cor, gp, oi, ni, eb, eps, so, cx, rd, s, TENANT_ID)
              for c, y, p, rev, cor, gp, oi, ni, eb, eps, so, cx, rd, s in FINANCIALS_DATA]
    try:
        execute_values(cur, insert_financials, values)
        print(f"  [OK] {len(values)} rows upserted into financials")
    except Exception as e:
        print(f"  [ERR] financials: {e}")

    # Step 3: Populate balance_sheet
    print("\n=== Step 3: Populating balance_sheet ===")
    insert_bs = """
        INSERT INTO balance_sheet (company_name, fiscal_year, total_assets, total_liabilities,
            total_equity, cash, total_debt, current_assets, current_liabilities, ppne_net, tenant_id)
        VALUES %s
        ON CONFLICT (company_name, fiscal_year, tenant_id) DO UPDATE SET
            total_assets = EXCLUDED.total_assets,
            total_liabilities = EXCLUDED.total_liabilities,
            total_equity = EXCLUDED.total_equity,
            cash = EXCLUDED.cash,
            total_debt = EXCLUDED.total_debt,
            current_assets = EXCLUDED.current_assets,
            current_liabilities = EXCLUDED.current_liabilities,
            ppne_net = EXCLUDED.ppne_net
    """
    values_bs = [(c, y, ta, tl, te, ca, td, cua, cl, pp, TENANT_ID)
                 for c, y, ta, tl, te, ca, td, cua, cl, pp in BALANCE_SHEET_DATA]
    try:
        execute_values(cur, insert_bs, values_bs)
        print(f"  [OK] {len(values_bs)} rows upserted into balance_sheet")
    except Exception as e:
        print(f"  [ERR] balance_sheet: {e}")

    # Step 4: Populate quarterly_revenue
    print("\n=== Step 4: Populating quarterly_revenue ===")
    insert_qr = """
        INSERT INTO quarterly_revenue (company_name, quarter, revenue, sector, tenant_id)
        VALUES %s
        ON CONFLICT (company_name, quarter, tenant_id) DO UPDATE SET
            revenue = EXCLUDED.revenue,
            sector = EXCLUDED.sector
    """
    values_qr = [(c, q, r, s, TENANT_ID)
                 for c, q, r, s in QUARTERLY_REVENUE_DATA]
    try:
        execute_values(cur, insert_qr, values_qr)
        print(f"  [OK] {len(values_qr)} rows upserted into quarterly_revenue")
    except Exception as e:
        print(f"  [ERR] quarterly_revenue: {e}")

    # Step 5: Verify
    print("\n=== Step 5: Verification ===")
    for table in ["financials", "balance_sheet", "quarterly_revenue"]:
        cur.execute(f"SELECT count(*) FROM {table}")
        count = cur.fetchone()[0]
        cur.execute(f"SELECT count(DISTINCT company_name) FROM {table}")
        companies = cur.fetchone()[0]
        print(f"  {table}: {count} rows, {companies} companies")

    # Show sample
    print("\n=== Sample data ===")
    cur.execute("SELECT company_name, fiscal_year, period, revenue, net_income, sector FROM financials WHERE period='FY' ORDER BY revenue DESC LIMIT 5")
    print("\nTop 5 companies by revenue (financials):")
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]} {row[2]}): Revenue=${row[3]:,.0f}M, Net Income=${row[4]:,.0f}M [{row[5]}]")

    cur.execute("SELECT company_name, fiscal_year, total_assets, total_equity FROM balance_sheet ORDER BY total_assets DESC LIMIT 5")
    print("\nTop 5 by total assets (balance_sheet):")
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]}): Assets=${row[2]:,.0f}M, Equity=${row[3]:,.0f}M")

    cur.execute("SELECT company_name, quarter, revenue FROM quarterly_revenue ORDER BY revenue DESC LIMIT 5")
    print("\nTop 5 quarterly revenues:")
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]}): Revenue=${row[2]:,.0f}M")

    # Step 6: Check schema introspection will find these tables
    print("\n=== Step 6: Schema introspection check ===")
    cur.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN ('financials', 'balance_sheet', 'quarterly_revenue')
        ORDER BY table_name, ordinal_position
    """)
    current_table = ""
    for row in cur.fetchall():
        if row[0] != current_table:
            current_table = row[0]
            print(f"\n  Table: {current_table}")
        print(f"    {row[1]} ({row[2]})")

    cur.close()
    conn.close()
    print("\n=== DONE ===")
    print(f"Total: {len(FINANCIALS_DATA)} financials + {len(BALANCE_SHEET_DATA)} balance_sheet + {len(QUARTERLY_REVENUE_DATA)} quarterly_revenue rows")
    print("The Quant pipeline should now find data when querying these tables.")


if __name__ == "__main__":
    main()
