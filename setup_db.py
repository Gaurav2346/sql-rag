import os
import sqlite3

DB = "data/demo.db"

SCHEMA = """
DROP TABLE IF EXISTS cust_mst;
DROP TABLE IF EXISTS ord_txn;
DROP TABLE IF EXISTS emp_rec;
DROP TABLE IF EXISTS prod_mst;

CREATE TABLE cust_mst (
    cust_id  INTEGER PRIMARY KEY,
    cust_nm  TEXT NOT NULL,
    st_cd    TEXT,
    city_nm  TEXT,
    crtd_dt  TEXT
);

CREATE TABLE prod_mst (
    prod_id  INTEGER PRIMARY KEY,
    prod_nm  TEXT NOT NULL,
    cat_cd   TEXT,
    unit_prc REAL
);

CREATE TABLE ord_txn (
    ord_id   INTEGER PRIMARY KEY,
    cust_id  INTEGER,
    prod_id  INTEGER,
    qty      INTEGER,
    amt      REAL,
    ord_dt   TEXT,
    stat_cd  INTEGER,
    FOREIGN KEY (cust_id) REFERENCES cust_mst(cust_id),
    FOREIGN KEY (prod_id) REFERENCES prod_mst(prod_id)
);

CREATE TABLE emp_rec (
    emp_id   INTEGER PRIMARY KEY,
    emp_nm   TEXT NOT NULL,
    dept_cd  TEXT,
    sal      REAL,
    join_dt  TEXT
);
"""

CUSTOMERS = [
    (101, "Rahul Verma",    "MH", "Mumbai",    "2023-04-12"),
    (102, "Priya Nair",     "KA", "Bengaluru", "2024-01-08"),
    (103, "Amit Shah",      "MH", "Pune",      "2024-06-30"),
    (104, "Sneha Iyer",     "TN", "Chennai",   "2023-11-02"),
    (105, "Vikram Singh",   "DL", "Delhi",     "2025-02-14"),
    (106, "Kavya Reddy",    "KA", "Mysuru",    "2024-09-19"),
    (107, "Arjun Deshmukh", "MH", "Nagpur",    "2025-05-05"),
]

PRODUCTS = [
    (1, "Laptop 14 inch",      "ELEC", 62000.0),
    (2, "Wireless Mouse",      "ACCS",   799.0),
    (3, "Office Chair",        "FURN",  8500.0),
    (4, "LED Monitor 24",      "ELEC", 11500.0),
    (5, "Mechanical Keyboard", "ACCS",  4200.0),
]

ORDERS = [
    (5001, 101, 1, 1,  62000.0, "2025-02-11", 3),
    (5002, 103, 2, 3,   2397.0, "2025-03-04", 3),
    (5003, 101, 4, 2,  23000.0, "2025-05-19", 2),
    (5004, 102, 3, 1,   8500.0, "2025-01-22", 3),
    (5005, 104, 1, 1,  62000.0, "2025-04-08", 1),
    (5006, 105, 5, 2,   8400.0, "2025-06-01", 3),
    (5007, 103, 4, 1,  11500.0, "2025-06-15", 4),
    (5008, 107, 1, 2, 124000.0, "2025-07-02", 3),
    (5009, 106, 2, 5,   3995.0, "2025-07-11", 2),
    (5010, 101, 3, 1,   8500.0, "2025-07-20", 1),
]

EMPLOYEES = [
    (1, "Meera Joshi",    "SALES",  85000.0, "2021-06-01"),
    (2, "Rohit Kulkarni", "TECH",  120000.0, "2020-03-15"),
    (3, "Anita Rao",      "SALES",  92000.0, "2022-08-09"),
    (4, "Sanjay Patil",   "OPS",    67000.0, "2023-01-30"),
]


def main():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)

    conn.executemany("INSERT INTO cust_mst VALUES (?,?,?,?,?)", CUSTOMERS)
    conn.executemany("INSERT INTO prod_mst VALUES (?,?,?,?)", PRODUCTS)
    conn.executemany("INSERT INTO ord_txn  VALUES (?,?,?,?,?,?,?)", ORDERS)
    conn.executemany("INSERT INTO emp_rec  VALUES (?,?,?,?,?)", EMPLOYEES)
    conn.commit()

    print(f"created {DB}")
    for t in ("cust_mst", "prod_mst", "ord_txn", "emp_rec"):
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:10} {n:3} rows")
    conn.close()


if __name__ == "__main__":
    main()