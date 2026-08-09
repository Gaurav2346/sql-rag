"""
Builds a LARGE toy database -- around 60 tables.

Why: with 4 tables, retrieval is pointless. You could paste the whole
schema into the prompt and it would work fine. The limitation we claim
to solve (L1: full schema does not fit) only becomes real at scale.

This database has enough tables that dumping the whole schema is
genuinely wasteful, so when retrieval picks the right 5, you can prove
it did something.

Run once:  python make_big_db.py
"""

import os
import sqlite3

DB = "data/big.db"

# (table, [(col, type)], rows_to_insert)
TABLES = [
    ("cust_mst", [("cust_id", "INTEGER PRIMARY KEY"), ("cust_nm", "TEXT"),
                  ("st_cd", "TEXT"), ("city_nm", "TEXT"), ("crtd_dt", "TEXT")]),
    ("ord_txn", [("ord_id", "INTEGER PRIMARY KEY"), ("cust_id", "INTEGER"),
                 ("prod_id", "INTEGER"), ("qty", "INTEGER"), ("amt", "REAL"),
                 ("ord_dt", "TEXT"), ("stat_cd", "INTEGER")]),
    ("prod_mst", [("prod_id", "INTEGER PRIMARY KEY"), ("prod_nm", "TEXT"),
                  ("cat_cd", "TEXT"), ("unit_prc", "REAL")]),
    ("emp_rec", [("emp_id", "INTEGER PRIMARY KEY"), ("emp_nm", "TEXT"),
                 ("dept_cd", "TEXT"), ("sal", "REAL"), ("join_dt", "TEXT")]),
]

# Filler tables. Real ERP systems are full of these -- audit logs, config
# tables, lookup tables, staging tables. They are noise for most questions,
# which is exactly what makes retrieval necessary.
FILLER = [
    ("inv_hdr", ["inv_id", "cust_id", "inv_dt", "tot_amt", "tax_amt"]),
    ("inv_ln", ["ln_id", "inv_id", "prod_id", "qty", "ln_amt"]),
    ("pay_txn", ["pay_id", "inv_id", "pay_dt", "pay_amt", "mode_cd"]),
    ("ship_hdr", ["ship_id", "ord_id", "carrier_cd", "ship_dt", "trk_no"]),
    ("ship_ln", ["sln_id", "ship_id", "prod_id", "qty"]),
    ("ret_req", ["ret_id", "ord_id", "rsn_cd", "req_dt", "stat_cd"]),
    ("wh_mst", ["wh_id", "wh_nm", "st_cd", "cap_units"]),
    ("stk_lvl", ["stk_id", "wh_id", "prod_id", "on_hand", "reorder_lvl"]),
    ("stk_mov", ["mov_id", "wh_id", "prod_id", "mov_typ", "qty", "mov_dt"]),
    ("supp_mst", ["supp_id", "supp_nm", "st_cd", "gstin", "rating"]),
    ("po_hdr", ["po_id", "supp_id", "po_dt", "tot_amt", "stat_cd"]),
    ("po_ln", ["pln_id", "po_id", "prod_id", "qty", "rate"]),
    ("grn_hdr", ["grn_id", "po_id", "recv_dt", "wh_id"]),
    ("grn_ln", ["gln_id", "grn_id", "prod_id", "qty_recv", "qty_rej"]),
    ("dept_mst", ["dept_cd", "dept_nm", "hod_emp_id", "budget"]),
    ("desig_mst", ["desig_cd", "desig_nm", "grade", "min_sal"]),
    ("attn_log", ["att_id", "emp_id", "att_dt", "in_tm", "out_tm"]),
    ("leave_req", ["lv_id", "emp_id", "lv_typ", "frm_dt", "to_dt", "stat_cd"]),
    ("payroll", ["pr_id", "emp_id", "mth", "gross", "ded", "net"]),
    ("appr_rec", ["apr_id", "emp_id", "cyc_yr", "rating", "hike_pct"]),
    ("cat_mst", ["cat_cd", "cat_nm", "parent_cd"]),
    ("brand_mst", ["brand_id", "brand_nm", "cntry_cd"]),
    ("price_hist", ["ph_id", "prod_id", "eff_dt", "old_prc", "new_prc"]),
    ("disc_rule", ["dr_id", "cat_cd", "min_qty", "disc_pct", "valid_to"]),
    ("promo_mst", ["promo_id", "promo_nm", "frm_dt", "to_dt", "disc_pct"]),
    ("cpn_mst", ["cpn_id", "cpn_cd", "promo_id", "used_flg"]),
    ("cart_hdr", ["cart_id", "cust_id", "crtd_dt", "stat_cd"]),
    ("cart_ln", ["cln_id", "cart_id", "prod_id", "qty"]),
    ("wish_lst", ["wl_id", "cust_id", "prod_id", "add_dt"]),
    ("rev_rec", ["rev_id", "prod_id", "cust_id", "rating", "cmnt", "rev_dt"]),
    ("tkt_hdr", ["tkt_id", "cust_id", "subj", "prio_cd", "stat_cd", "opn_dt"]),
    ("tkt_msg", ["msg_id", "tkt_id", "sender_typ", "body", "sent_dt"]),
    ("addr_bk", ["addr_id", "cust_id", "line1", "city_nm", "st_cd", "pin_cd"]),
    ("st_mst", ["st_cd", "st_nm", "regn_cd"]),
    ("regn_mst", ["regn_cd", "regn_nm"]),
    ("cntry_mst", ["cntry_cd", "cntry_nm", "curr_cd"]),
    ("curr_rt", ["rt_id", "curr_cd", "eff_dt", "rate"]),
    ("tax_slab", ["slab_id", "cat_cd", "gst_pct", "eff_dt"]),
    ("led_hdr", ["led_id", "acct_cd", "txn_dt", "dr_amt", "cr_amt"]),
    ("acct_mst", ["acct_cd", "acct_nm", "acct_typ"]),
    ("bank_txn", ["btx_id", "acct_cd", "txn_dt", "amt", "ref_no"]),
    ("budget_ln", ["bl_id", "dept_cd", "fy", "alloc_amt", "spent_amt"]),
    ("asset_reg", ["ast_id", "ast_nm", "dept_cd", "purch_dt", "wdv"]),
    ("veh_mst", ["veh_id", "reg_no", "typ_cd", "cap_kg"]),
    ("route_mst", ["rt_id", "frm_city", "to_city", "dist_km"]),
    ("trip_log", ["trip_id", "veh_id", "rt_id", "strt_dt", "end_dt"]),
    ("fuel_log", ["fl_id", "veh_id", "fill_dt", "litres", "amt"]),
    ("usr_mst", ["usr_id", "login_nm", "emp_id", "role_cd", "actv_flg"]),
    ("role_mst", ["role_cd", "role_nm", "lvl"]),
    ("perm_map", ["pm_id", "role_cd", "res_cd", "can_rd", "can_wr"]),
    ("audit_log", ["aud_id", "usr_id", "actn", "tbl_nm", "rec_id", "ts"]),
    ("cfg_prm", ["prm_cd", "prm_val", "upd_dt"]),
    ("job_sched", ["job_id", "job_nm", "cron_exp", "last_run"]),
    ("job_run", ["run_id", "job_id", "strt_ts", "end_ts", "stat_cd"]),
    ("notif_q", ["nq_id", "usr_id", "chnl_cd", "body", "sent_flg"]),
    ("eml_log", ["eml_id", "to_addr", "subj", "sent_ts", "stat_cd"]),
    ("sms_log", ["sms_id", "mob_no", "body", "sent_ts", "stat_cd"]),
    ("stg_import", ["stg_id", "src_file", "row_no", "raw_json", "proc_flg"]),
    ("err_log", ["err_id", "modu_cd", "err_msg", "ts"]),
]

CUSTOMERS = [
    (101, "Rahul Verma", "MH", "Mumbai", "2023-04-12"),
    (102, "Priya Nair", "KA", "Bengaluru", "2024-01-08"),
    (103, "Amit Shah", "MH", "Pune", "2024-06-30"),
    (104, "Sneha Iyer", "TN", "Chennai", "2023-11-02"),
    (105, "Vikram Singh", "DL", "Delhi", "2025-02-14"),
    (106, "Kavya Reddy", "KA", "Mysuru", "2024-09-19"),
    (107, "Arjun Deshmukh", "MH", "Nagpur", "2025-05-05"),
]

PRODUCTS = [
    (1, "Laptop 14 inch", "ELEC", 62000.0),
    (2, "Wireless Mouse", "ACCS", 799.0),
    (3, "Office Chair", "FURN", 8500.0),
    (4, "LED Monitor 24", "ELEC", 11500.0),
    (5, "Mechanical Keyboard", "ACCS", 4200.0),
]

ORDERS = [
    (5001, 101, 1, 1, 62000.0, "2025-02-11", 3),
    (5002, 103, 2, 3, 2397.0, "2025-03-04", 3),
    (5003, 101, 4, 2, 23000.0, "2025-05-19", 2),
    (5004, 102, 3, 1, 8500.0, "2025-01-22", 3),
    (5005, 104, 1, 1, 62000.0, "2025-04-08", 1),
    (5006, 105, 5, 2, 8400.0, "2025-06-01", 3),
    (5007, 103, 4, 1, 11500.0, "2025-06-15", 4),
    (5008, 107, 1, 2, 124000.0, "2025-07-02", 3),
    (5009, 106, 2, 5, 3995.0, "2025-07-11", 2),
    (5010, 101, 3, 1, 8500.0, "2025-07-20", 1),
]

EMPLOYEES = [
    (1, "Meera Joshi", "SALES", 85000.0, "2021-06-01"),
    (2, "Rohit Kulkarni", "TECH", 120000.0, "2020-03-15"),
    (3, "Anita Rao", "SALES", 92000.0, "2022-08-09"),
    (4, "Sanjay Patil", "OPS", 67000.0, "2023-01-30"),
]

STATES = [("MH", "Maharashtra", "WEST"), ("KA", "Karnataka", "SOUTH"),
          ("TN", "Tamil Nadu", "SOUTH"), ("DL", "Delhi", "NORTH"),
          ("GJ", "Gujarat", "WEST"), ("UP", "Uttar Pradesh", "NORTH")]


def main():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)

    for name, cols in TABLES:
        col_sql = ", ".join(f"{c} {t}" for c, t in cols)
        conn.execute(f"CREATE TABLE {name} ({col_sql})")

    for name, cols in FILLER:
        col_sql = ", ".join(f"{c} TEXT" for c in cols)
        conn.execute(f"CREATE TABLE {name} ({col_sql})")

    conn.executemany("INSERT INTO cust_mst VALUES (?,?,?,?,?)", CUSTOMERS)
    conn.executemany("INSERT INTO prod_mst VALUES (?,?,?,?)", PRODUCTS)
    conn.executemany("INSERT INTO ord_txn  VALUES (?,?,?,?,?,?,?)", ORDERS)
    conn.executemany("INSERT INTO emp_rec  VALUES (?,?,?,?,?)", EMPLOYEES)
    conn.executemany("INSERT INTO st_mst   VALUES (?,?,?)", STATES)
    conn.commit()

    n = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    print(f"created {DB} with {n} tables")
    print("  populated: cust_mst, prod_mst, ord_txn, emp_rec, st_mst")
    print("  remaining tables are empty -- they exist to make the schema large")
    conn.close()


if __name__ == "__main__":
    main()