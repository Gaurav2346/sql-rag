"""
WEEK 4 -- business glossary for encoded database values.

Some database values have meanings that cannot be discovered from the
stored value itself.

Example:
    ord_txn.stat_cd = 3  -> delivered

The database only stores 3, so embeddings cannot infer "delivered".
This small dictionary acts like enterprise metadata / a business glossary.

Key format:
    (table_name, column_name, stored_value): [natural-language aliases]
"""

VALUE_ALIASES = {
    # ---------------- customer states ----------------
    ("cust_mst", "st_cd", "MH"): [
        "Maharashtra",
        "Maharashtra state",
    ],
    ("cust_mst", "st_cd", "KA"): [
        "Karnataka",
        "Karnataka state",
    ],
    ("cust_mst", "st_cd", "TN"): [
        "Tamil Nadu",
        "Tamil Nadu state",
    ],
    ("cust_mst", "st_cd", "DL"): [
        "Delhi",
        "Delhi state",
    ],

    # ---------------- product categories ----------------
    ("prod_mst", "cat_cd", "ELEC"): [
        "electronics",
        "electronic products",
    ],
    ("prod_mst", "cat_cd", "ACCS"): [
        "accessories",
        "product accessories",
    ],
    ("prod_mst", "cat_cd", "FURN"): [
        "furniture",
        "office furniture",
    ],

    # ---------------- employee departments ----------------
    ("emp_rec", "dept_cd", "SALES"): [
        "sales",
        "sales department",
    ],
    ("emp_rec", "dept_cd", "TECH"): [
        "technology",
        "technology department",
        "tech department",
    ],
    ("emp_rec", "dept_cd", "OPS"): [
        "operations",
        "operations department",
    ],

    # ---------------- order status codes ----------------
    ("ord_txn", "stat_cd", "1"): [
        "pending",
        "pending order",
    ],
    ("ord_txn", "stat_cd", "2"): [
        "processing",
        "in progress",
        "processing order",
    ],
    ("ord_txn", "stat_cd", "3"): [
        "delivered",
        "delivered order",
        "completed delivery",
    ],
    ("ord_txn", "stat_cd", "4"): [
        "cancelled",
        "canceled",
        "cancelled order",
    ],
}