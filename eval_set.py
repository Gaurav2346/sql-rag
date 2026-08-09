"""
WEEK 3 -- the evaluation set.

20 questions with their correct ("gold") SQL, hand-written against the
populated tables of big.db. This is our mini-benchmark: it lets us
measure accuracy on data we fully understand, before pointing the same
harness at BIRD.

Difficulty tiers mirror BIRD's own taxonomy:
    easy   -- single table, simple filter or count
    medium -- one join, or grouping/aggregation
    hard   -- multiple joins, or value mapping, or subtlety

Every gold SQL here has been run and verified to return sensible rows.
The question wording deliberately uses plain English ("buyers",
"Maharashtra") that does NOT match the cryptic schema -- that is the
whole point of the project.
"""

EVAL_SET = [
    # ---------------- easy ----------------
    {
        "id": "e01",
        "q": "How many customers do we have?",
        "sql": "SELECT COUNT(*) FROM cust_mst",
        "level": "easy",
    },
    {
        "id": "e02",
        "q": "List all customers from Maharashtra.",
        "sql": "SELECT cust_nm FROM cust_mst WHERE st_cd = 'MH'",
        "level": "easy",
    },
    {
        "id": "e03",
        "q": "How many orders were placed in July 2025?",
        "sql": "SELECT COUNT(*) FROM ord_txn WHERE ord_dt LIKE '2025-07%'",
        "level": "easy",
    },
    {
        "id": "e04",
        "q": "What is the most expensive product?",
        "sql": "SELECT prod_nm FROM prod_mst ORDER BY unit_prc DESC LIMIT 1",
        "level": "easy",
    },
    {
        "id": "e05",
        "q": "Which employees work in the sales department?",
        "sql": "SELECT emp_nm FROM emp_rec WHERE dept_cd = 'SALES'",
        "level": "easy",
    },
    {
        "id": "e06",
        "q": "How many products cost more than 10000?",
        "sql": "SELECT COUNT(*) FROM prod_mst WHERE unit_prc > 10000",
        "level": "easy",
    },
    {
        "id": "e07",
        "q": "List all customers from Karnataka.",
        "sql": "SELECT cust_nm FROM cust_mst WHERE st_cd = 'KA'",
        "level": "easy",
    },

    # ---------------- medium ----------------
    {
        "id": "m01",
        "q": "What is the total sales amount across all orders?",
        "sql": "SELECT SUM(amt) FROM ord_txn",
        "level": "medium",
    },
    {
        "id": "m02",
        "q": "Who are our top customers by total spend?",
        "sql": ("SELECT c.cust_nm, SUM(o.amt) AS total FROM cust_mst c "
                "JOIN ord_txn o ON c.cust_id = o.cust_id "
                "GROUP BY c.cust_id ORDER BY total DESC"),
        "level": "medium",
    },
    {
        "id": "m03",
        "q": "How many orders has each customer placed?",
        "sql": ("SELECT c.cust_nm, COUNT(o.ord_id) AS n FROM cust_mst c "
                "JOIN ord_txn o ON c.cust_id = o.cust_id "
                "GROUP BY c.cust_id"),
        "level": "medium",
    },
    {
        "id": "m04",
        "q": "What is the average salary by department?",
        "sql": "SELECT dept_cd, AVG(sal) FROM emp_rec GROUP BY dept_cd",
        "level": "medium",
    },
    {
        "id": "m05",
        "q": "Which products have been ordered at least once?",
        "sql": ("SELECT DISTINCT p.prod_nm FROM prod_mst p "
                "JOIN ord_txn o ON p.prod_id = o.prod_id"),
        "level": "medium",
    },
    {
        "id": "m06",
        "q": "How many delivered orders are there?",
        "sql": "SELECT COUNT(*) FROM ord_txn WHERE stat_cd = 3",
        "level": "medium",
    },
    {
        "id": "m07",
        "q": "What is the highest-value single order?",
        "sql": "SELECT MAX(amt) FROM ord_txn",
        "level": "medium",
    },

    # ---------------- hard ----------------
    {
        "id": "h01",
        "q": "Which customer spent the most in total?",
        "sql": ("SELECT c.cust_nm FROM cust_mst c "
                "JOIN ord_txn o ON c.cust_id = o.cust_id "
                "GROUP BY c.cust_id ORDER BY SUM(o.amt) DESC LIMIT 1"),
        "level": "hard",
    },
    {
        "id": "h02",
        "q": "What products did Rahul Verma order?",
        "sql": ("SELECT DISTINCT p.prod_nm FROM cust_mst c "
                "JOIN ord_txn o ON c.cust_id = o.cust_id "
                "JOIN prod_mst p ON o.prod_id = p.prod_id "
                "WHERE c.cust_nm = 'Rahul Verma'"),
        "level": "hard",
    },
    {
        "id": "h03",
        "q": "What is the total spend by customers from Maharashtra?",
        "sql": ("SELECT SUM(o.amt) FROM cust_mst c "
                "JOIN ord_txn o ON c.cust_id = o.cust_id "
                "WHERE c.st_cd = 'MH'"),
        "level": "hard",
    },
    {
        "id": "h04",
        "q": "Which product category has the most products?",
        "sql": ("SELECT cat_cd FROM prod_mst "
                "GROUP BY cat_cd ORDER BY COUNT(*) DESC LIMIT 1"),
        "level": "hard",
    },
    {
        "id": "h05",
        "q": "List customers who have never placed an order.",
        "sql": ("SELECT cust_nm FROM cust_mst WHERE cust_id NOT IN "
                "(SELECT DISTINCT cust_id FROM ord_txn)"),
        "level": "hard",
    },
    {
        "id": "h06",
        "q": "Which pending orders are worth more than 8000?",
        "sql": "SELECT ord_id FROM ord_txn WHERE stat_cd = 1 AND amt > 8000",
        "level": "hard",
    },
]


def by_level():
    out = {}
    for item in EVAL_SET:
        out.setdefault(item["level"], []).append(item)
    return out


if __name__ == "__main__":
    # Verify every gold SQL runs and returns something sensible.
    import sqlite3
    conn = sqlite3.connect("data/big.db")
    print(f"{'id':5} {'level':7} rows  question")
    print("-" * 60)
    for item in EVAL_SET:
        try:
            rows = conn.execute(item["sql"]).fetchall()
            print(f"{item['id']:5} {item['level']:7} {len(rows):4}  {item['q']}")
        except Exception as e:
            print(f"{item['id']:5} {item['level']:7} FAIL  {e}")
    conn.close()