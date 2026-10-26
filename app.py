import sqlite3
from datetime import date as date_type
from textwrap import dedent

import pandas as pd
import streamlit as st

from config import CONFIG
from week2 import ask
from demo_cache import (
    get_demo_answer,
    refresh_demo_answers,
)
from auth import (
    apply_style,
    logout_user,
    require_login,
)


# ============================================================
# DATABASE
# ============================================================

DB = "data/big.db"


CRUD_TABLES = {
    "Customers": {
        "table": "cust_mst",
        "key": "cust_id",
        "label": "customer",
        "fields": [
            ("cust_nm", "Customer name", "text"),
            ("st_cd", "State code", "state"),
            ("city_nm", "City", "text"),
            ("crtd_dt", "Created date", "date"),
        ],
    },
    "Products": {
        "table": "prod_mst",
        "key": "prod_id",
        "label": "product",
        "fields": [
            ("prod_nm", "Product name", "text"),
            ("cat_cd", "Category", "category"),
            ("unit_prc", "Unit price", "float"),
        ],
    },
    "Orders": {
        "table": "ord_txn",
        "key": "ord_id",
        "label": "order",
        "fields": [
            ("cust_id", "Customer", "customer_id"),
            ("prod_id", "Product", "product_id"),
            ("qty", "Quantity", "int"),
            ("amt", "Order amount", "float"),
            ("ord_dt", "Order date", "date"),
            ("stat_cd", "Status code (1=pending, 2=processing, 3=delivered, 4=cancelled)", "status"),
        ],
    },
    "Employees": {
        "table": "emp_rec",
        "key": "emp_id",
        "label": "employee",
        "fields": [
            ("emp_nm", "Employee name", "text"),
            ("dept_cd", "Department", "department"),
            ("sal", "Salary", "float"),
            ("join_dt", "Join date", "date"),
        ],
    },
}

CRUD_TABLES_BY_NAME = {
    definition["table"]: definition for definition in CRUD_TABLES.values()
}


def field_options(conn, kind):
    if kind == "state":
        rows = conn.execute(
            "SELECT DISTINCT st_cd FROM cust_mst "
            "WHERE st_cd IS NOT NULL ORDER BY st_cd"
        ).fetchall()
        return [row[0] for row in rows]
    if kind == "category":
        return [row[0] for row in conn.execute(
            "SELECT DISTINCT cat_cd FROM prod_mst WHERE cat_cd IS NOT NULL ORDER BY cat_cd"
        )]
    if kind == "department":
        return [row[0] for row in conn.execute(
            "SELECT DISTINCT dept_cd FROM emp_rec WHERE dept_cd IS NOT NULL ORDER BY dept_cd"
        )]
    if kind == "status":
        return [1, 2, 3, 4]
    if kind == "customer_id":
        return [row[0] for row in conn.execute(
            "SELECT cust_id FROM cust_mst ORDER BY cust_nm"
        )]
    if kind == "product_id":
        return [row[0] for row in conn.execute(
            "SELECT prod_id FROM prod_mst ORDER BY prod_nm"
        )]
    return []


def field_label(conn, kind, value):
    if kind == "customer_id":
        row = conn.execute(
            "SELECT cust_nm FROM cust_mst WHERE cust_id = ?", (value,)
        ).fetchone()
        return f"{row[0]} (ID {value})" if row else str(value)
    if kind == "product_id":
        row = conn.execute(
            "SELECT prod_nm FROM prod_mst WHERE prod_id = ?", (value,)
        ).fetchone()
        return f"{row[0]} (ID {value})" if row else str(value)
    return str(value)


def form_field(conn, field, value=None, key="field"):
    column, label, kind = field
    if kind in ("customer_id", "product_id"):
        table, id_column = (
            ("cust_mst", "cust_id") if kind == "customer_id"
            else ("prod_mst", "prod_id")
        )
        max_id = conn.execute(
            f"SELECT COALESCE(MAX({id_column}), 1) FROM {table}"
        ).fetchone()[0]
        st.caption(f"Enter an existing ID from the {table} table.")
        return int(st.number_input(
            label,
            min_value=1,
            max_value=max(1, int(max_id)),
            value=int(value or 1),
            step=1,
            key=key,
        ))
    if kind in ("state", "category", "department", "status", "customer_id", "product_id"):
        options = field_options(conn, kind)
        if not options:
            st.warning(f"Add a {kind.replace('_id', '')} before using this field.")
            return None
        index = options.index(value) if value in options else 0
        return st.selectbox(
            label,
            options,
            index=index,
            key=key,
            format_func=lambda option: field_label(conn, kind, option),
        )
    if kind == "date":
        try:
            default = date_type.fromisoformat(str(value)) if value else date_type.today()
        except ValueError:
            default = date_type.today()
        return st.date_input(label, value=default, key=key).isoformat()
    if kind == "int":
        return int(st.number_input(label, min_value=0, step=1, value=int(value or 1), key=key))
    if kind == "float":
        return float(st.number_input(label, min_value=0.0, step=100.0, value=float(value or 0.0), key=key))
    return st.text_input(label, value="" if value is None else str(value), key=key)


def refresh_after_mutation(conn):
    conn.commit()
    refresh_demo_answers(conn)


def quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def get_database_tables(conn):
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]


def get_table_inventory(conn):
    inventory = []
    for table_name in get_database_tables(conn):
        quoted = quote_identifier(table_name)
        count = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
        columns = conn.execute(f"PRAGMA table_info({quoted})").fetchall()
        primary_keys = [column[1] for column in columns if column[5]]
        inventory.append({
            "Table": table_name,
            "Rows": count,
            "Columns": len(columns),
            "Primary key": ", ".join(primary_keys) if primary_keys else "rowid",
        })
    return pd.DataFrame(inventory)


def render_dashboard_cards(items, layout):
    cards = "".join(
        dedent(f"""\
        <article class="dashboard-stat-card {accent}">
            <div class="dashboard-stat-top">
                <span class="dashboard-stat-icon">{icon}</span>
                <span class="dashboard-stat-tag">LIVE</span>
            </div>
            <div class="dashboard-stat-label">{label}</div>
            <div class="dashboard-stat-value">{value}</div>
            <div class="dashboard-stat-foot"><span>●</span>{description}</div>
        </article>
        """).strip()
        for icon, label, value, description, accent in items
    )
    st.html(f'<div class="dashboard-card-grid {layout}">{cards}</div>')


def generic_form_field(column, value=None, key="generic_field"):
    name, declared_type = column[1], (column[2] or "TEXT").upper()
    label = name.replace("_", " ").title()
    if "INT" in declared_type:
        return int(st.number_input(label, value=int(value or 0), step=1, key=key))
    if any(part in declared_type for part in ("REAL", "FLOA", "DOUB", "NUM")):
        return float(st.number_input(label, value=float(value or 0), key=key))
    current = "" if value is None else str(value)
    if len(current) > 120 or any(term in name.lower() for term in ("body", "json", "message", "desc")):
        return st.text_area(label, value=current, key=key, height=100)
    return st.text_input(label, value=current, key=key)


def render_generic_table(conn, table_name):
    quoted_table = quote_identifier(table_name)
    columns = conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
    column_names = [column[1] for column in columns]
    primary_key_columns = [column for column in columns if column[5]]
    page_size = 100
    record_count = conn.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
    page_count = max(1, (record_count + page_size - 1) // page_size)
    selected_page = st.selectbox(
        "Browse records",
        list(range(1, page_count + 1)),
        format_func=lambda page: f"Page {page} of {page_count}",
        key=f"generic_page_{table_name}",
    )
    offset = (selected_page - 1) * page_size
    rows = conn.execute(
        f"SELECT rowid AS __rowid__, * FROM {quoted_table} ORDER BY rowid LIMIT ? OFFSET ?",
        (page_size, offset),
    ).fetchall()
    display = pd.DataFrame(rows, columns=["__rowid__"] + column_names)
    first = offset + 1 if record_count else 0
    last = min(offset + len(rows), record_count)
    st.markdown(f"### {table_name} records")
    st.caption(f"{record_count:,} total records · Showing {first:,}–{last:,} · {len(columns)} columns")
    search = st.text_input(
        "Filter records on this page",
        placeholder=f"Search these {len(rows):,} records…",
        key=f"generic_search_{table_name}",
        label_visibility="collapsed",
    )
    if search.strip() and not display.empty:
        matches = display.astype(str).apply(
            lambda series: series.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        display = display.loc[matches]
    st.caption(f"{len(display):,} matching record(s) on this page")
    st.dataframe(display.drop(columns=["__rowid__"], errors="ignore"), use_container_width=True, hide_index=True)

    add_tab, edit_tab, delete_tab = st.tabs(["＋ Add record", "✎ Edit record", "⌫ Delete record"])
    insert_columns = [column for column in columns if not (column[5] and "INT" in (column[2] or "").upper())]
    with add_tab:
        st.caption("Complete the fields to add a record to this table.")
        with st.form(f"generic_add_{table_name}"):
            values = [
                generic_form_field(column, key=f"generic_add_{table_name}_{column[1]}")
                for column in insert_columns
            ]
            if st.form_submit_button("Create record", type="primary"):
                try:
                    names = ", ".join(quote_identifier(column[1]) for column in insert_columns)
                    placeholders = ", ".join("?" for _ in insert_columns)
                    conn.execute(
                        f"INSERT INTO {quoted_table} ({names}) VALUES ({placeholders})", values
                    )
                    refresh_after_mutation(conn)
                    st.success(f"Record added to {table_name}.")
                    st.rerun()
                except sqlite3.Error as error:
                    st.error(f"Could not create record: {error}")

    with edit_tab:
        st.caption("Select a record from this page, update its fields, and save.")
        if rows:
            selected_rowid = st.selectbox(
                "Select record",
                [row[0] for row in rows],
                key=f"generic_edit_select_{table_name}",
                format_func=lambda rowid: f"Record {rowid}",
            )
            selected_record = conn.execute(
                f"SELECT * FROM {quoted_table} WHERE rowid = ?", (selected_rowid,)
            ).fetchone()
            with st.form(f"generic_edit_{table_name}"):
                edited_values = [
                    generic_form_field(
                        column,
                        selected_record[index],
                        key=f"generic_edit_{table_name}_{selected_rowid}_{column[1]}",
                    )
                    for index, column in enumerate(columns)
                    if column not in primary_key_columns
                ]
                editable_columns = [column for column in columns if column not in primary_key_columns]
                if st.form_submit_button("Save changes", disabled=not editable_columns):
                    try:
                        assignments = ", ".join(
                            f"{quote_identifier(column[1])} = ?" for column in editable_columns
                        )
                        conn.execute(
                            f"UPDATE {quoted_table} SET {assignments} WHERE rowid = ?",
                            edited_values + [selected_rowid],
                        )
                        refresh_after_mutation(conn)
                        st.success(f"Record updated in {table_name}.")
                        st.rerun()
                    except sqlite3.Error as error:
                        st.error(f"Could not update record: {error}")
        else:
            st.info("No records to edit yet.")

    with delete_tab:
        st.caption("Delete a record by its row ID. This action cannot be undone.")
        if rows:
            selected_delete_rowid = st.selectbox(
                "Select record to delete",
                [row[0] for row in rows],
                key=f"generic_delete_select_{table_name}",
                format_func=lambda rowid: f"Record {rowid}",
            )
            with st.form(f"generic_delete_{table_name}"):
                confirmed = st.checkbox("I confirm this deletion", key=f"generic_delete_confirm_{table_name}")
                if st.form_submit_button("Delete record", disabled=not confirmed):
                    try:
                        conn.execute(f"DELETE FROM {quoted_table} WHERE rowid = ?", (selected_delete_rowid,))
                        refresh_after_mutation(conn)
                        st.success(f"Record deleted from {table_name}.")
                        st.rerun()
                    except sqlite3.Error as error:
                        st.error(f"Could not delete record: {error}")
        else:
            st.info("No records to delete yet.")


def render_crud_table(conn, title, definition):
    table = definition["table"]
    key_column = definition["key"]
    fields = definition["fields"]
    page_size = 100
    record_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    page_count = max(1, (record_count + page_size - 1) // page_size)
    page_options = list(range(1, page_count + 1))
    selected_page = st.selectbox(
        "Browse records",
        page_options,
        format_func=lambda page: f"Page {page} of {page_count}",
        key=f"crud_page_{table}",
        help=f"Showing {page_size} records per page so large tables stay responsive.",
    )
    offset = (selected_page - 1) * page_size
    records = conn.execute(
        f"SELECT * FROM {table} ORDER BY {key_column} LIMIT ? OFFSET ?",
        (page_size, offset),
    ).fetchall()
    columns = [description[0] for description in conn.execute(
        f"SELECT * FROM {table} LIMIT 0"
    ).description]

    first_record = offset + 1 if record_count else 0
    last_record = min(offset + len(records), record_count)
    st.markdown(f"### {title} records")
    st.caption(f"Showing {first_record:,}–{last_record:,} of {record_count:,}. Browse using the page selector above.")
    search = st.text_input(
        "Filter this page",
        placeholder=f"Search these {len(records):,} records…",
        key=f"crud_search_{table}",
        label_visibility="collapsed",
    )
    display_records = pd.DataFrame(records, columns=columns)
    if search.strip() and not display_records.empty:
        matching = display_records.astype(str).apply(
            lambda column: column.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        display_records = display_records.loc[matching]
    st.caption(f"{len(display_records):,} matching record(s) on this page")
    st.dataframe(
        display_records,
        use_container_width=True,
        hide_index=True,
    )

    add_tab, edit_tab, delete_tab = st.tabs(["＋ Add record", "✎ Edit record", "⌫ Delete record"])
    with add_tab:
        with st.form(f"add_{table}"):
            st.markdown(f"#### Create a {definition['label']}")
            st.caption("Enter the details below. The database will assign the record ID automatically.")
            new_values = [
                form_field(conn, field, key=f"add_{table}_{field[0]}")
                for field in fields
            ]
            if st.form_submit_button(f"Create {definition['label'].title()}", type="primary"):
                try:
                    placeholders = ", ".join("?" for _ in fields)
                    field_names = ", ".join(field[0] for field in fields)
                    conn.execute(
                        f"INSERT INTO {table} ({field_names}) VALUES ({placeholders})",
                        new_values,
                    )
                    refresh_after_mutation(conn)
                    st.success(f"{definition['label'].title()} created.")
                    st.rerun()
                except sqlite3.Error as error:
                    st.error(f"Could not create record: {error}")

    with edit_tab:
        with st.form(f"edit_{table}"):
            st.markdown(f"#### Update a {definition['label']}")
            st.caption("Choose a record from the current page, make changes, and save.")
            selected_id = None
            edited_values = []
            if records:
                selected_id = st.selectbox(
                    f"Select {definition['label']}",
                    [record[columns.index(key_column)] for record in records],
                    key=f"edit_select_{table}",
                    format_func=lambda record_id: f"{record_id} — " + str(
                        conn.execute(
                            f"SELECT {fields[0][0]} FROM {table} WHERE {key_column} = ?",
                            (record_id,),
                        ).fetchone()[0]
                    ),
                )
                selected_record = conn.execute(
                    f"SELECT * FROM {table} WHERE {key_column} = ?", (selected_id,)
                ).fetchone()
                for field in fields:
                    field_index = columns.index(field[0])
                    edited_values.append(
                        form_field(
                            conn,
                            field,
                            selected_record[field_index],
                            key=f"edit_{table}_{selected_id}_{field[0]}",
                        )
                    )
            else:
                st.info("No records to edit yet.")

            if st.form_submit_button("Save Changes", disabled=not records):
                try:
                    assignments = ", ".join(f"{field[0]} = ?" for field in fields)
                    conn.execute(
                        f"UPDATE {table} SET {assignments} WHERE {key_column} = ?",
                        edited_values + [selected_id],
                    )
                    refresh_after_mutation(conn)
                    st.success(f"{definition['label'].title()} updated.")
                    st.rerun()
                except sqlite3.Error as error:
                    st.error(f"Could not update record: {error}")

    with delete_tab:
        with st.form(f"delete_{table}"):
            st.markdown(f"#### Remove a {definition['label']}")
            st.caption("Deletion is permanent. Records referenced by existing orders are protected.")
            if records:
                selected_delete_id = st.selectbox(
                    f"Select {definition['label']} to delete",
                    [record[columns.index(key_column)] for record in records],
                    key=f"delete_select_{table}",
                    format_func=lambda record_id: f"{record_id} — " + str(
                        conn.execute(
                            f"SELECT {fields[0][0]} FROM {table} WHERE {key_column} = ?",
                            (record_id,),
                        ).fetchone()[0]
                    ),
                )
                confirmed = st.checkbox(
                    "I confirm this deletion",
                    key=f"delete_confirm_{table}",
                )
            else:
                selected_delete_id = None
                confirmed = False
                st.info("No records to delete.")

            if st.form_submit_button("Delete Record", disabled=not records):
                if not confirmed:
                    st.error("Confirm the deletion first.")
                else:
                    try:
                        if table == "cust_mst":
                            dependent_orders = conn.execute(
                                "SELECT COUNT(*) FROM ord_txn WHERE cust_id = ?",
                                (selected_delete_id,),
                            ).fetchone()[0]
                            if dependent_orders:
                                st.error(
                                    "This customer has orders. Delete or reassign those orders first."
                                )
                                st.stop()
                        if table == "prod_mst":
                            dependent_orders = conn.execute(
                                "SELECT COUNT(*) FROM ord_txn WHERE prod_id = ?",
                                (selected_delete_id,),
                            ).fetchone()[0]
                            if dependent_orders:
                                st.error(
                                    "This product appears in orders. Delete or reassign those orders first."
                                )
                                st.stop()
                        conn.execute(
                            f"DELETE FROM {table} WHERE {key_column} = ?",
                            (selected_delete_id,),
                        )
                        refresh_after_mutation(conn)
                        st.success(f"{definition['label'].title()} deleted.")
                        st.rerun()
                    except sqlite3.Error as error:
                        st.error(f"Could not delete record: {error}")


# ============================================================
# STREAMLIT PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Enterprise Data Dashboard",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# AUTH
# ============================================================

apply_style()

require_login()

st.markdown(
    """
    <style>
    .block-container {
        width: min(1760px, calc(100vw - 64px));
        max-width: 1760px;
        padding-top: 1.5rem;
        padding-left: clamp(1rem, 2.5vw, 2.75rem);
        padding-right: clamp(1rem, 2.5vw, 2.75rem);
        padding-bottom: 3rem;
    }

    .stApp {
        background:
            radial-gradient(ellipse at 50% -15%, rgba(83, 58, 160, .22), transparent 58%),
            linear-gradient(145deg, #0d1018 0%, #10131d 52%, #11121b 100%);
    }

    .stApp::before,
    .stApp::after {
        content: "";
        position: fixed;
        z-index: 0;
        width: min(34vw, 520px);
        aspect-ratio: 1;
        border-radius: 50%;
        filter: blur(85px);
        opacity: .25;
        pointer-events: none;
        animation: ambient-drift 17s ease-in-out infinite alternate;
    }

    .stApp::before {
        top: 22vh;
        left: -19vw;
        background: radial-gradient(circle, rgba(91, 78, 230, .72), rgba(91, 78, 230, 0) 68%);
    }

    .stApp::after {
        right: -19vw;
        bottom: 4vh;
        background: radial-gradient(circle, rgba(17, 160, 190, .55), rgba(17, 160, 190, 0) 68%);
        animation-delay: -8s;
    }

    @keyframes ambient-drift {
        from { transform: translate3d(0, -18px, 0) scale(.96); }
        to { transform: translate3d(32px, 24px, 0) scale(1.08); }
    }

    @keyframes soft-enter {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes view-arrive {
        from { opacity: 0; transform: translateY(16px) scale(.992); filter: blur(3px); }
        to { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
    }

    @keyframes result-glow {
        0%, 100% { box-shadow: 0 0 0 rgba(139, 92, 246, 0); }
        50% { box-shadow: 0 0 24px rgba(139, 92, 246, .12); }
    }

    @keyframes card-shimmer {
        from { transform: translateX(-130%) rotate(18deg); }
        to { transform: translateX(260%) rotate(18deg); }
    }

    .dashboard-card-grid {
        display: grid;
        gap: 1rem;
        margin: .35rem 0 1.15rem;
    }

    .dashboard-card-grid.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .dashboard-card-grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .dashboard-card-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }

    .dashboard-stat-card {
        --card-accent: #a78bfa;
        position: relative;
        isolation: isolate;
        overflow: hidden;
        min-height: 158px;
        padding: 1.1rem 1.2rem 1rem;
        border: 1px solid color-mix(in srgb, var(--card-accent) 42%, transparent);
        border-radius: 20px;
        background:
            radial-gradient(circle at 95% 0%, color-mix(in srgb, var(--card-accent) 22%, transparent), transparent 42%),
            linear-gradient(145deg, rgba(30, 34, 54, .96), rgba(25, 27, 39, .96) 58%, rgba(37, 29, 40, .96));
        box-shadow: 0 12px 32px rgba(0, 0, 0, .22), inset 0 1px rgba(255,255,255,.07);
        animation: soft-enter .62s cubic-bezier(.2,.7,.25,1) both;
        transition: transform .24s ease, border-color .24s ease, box-shadow .24s ease;
    }

    .dashboard-stat-card::before {
        position: absolute;
        z-index: 1;
        top: -70%;
        left: -28%;
        width: 35%;
        height: 240%;
        content: "";
        background: linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent);
        opacity: 0;
        pointer-events: none;
    }

    .dashboard-stat-card:hover {
        transform: translateY(-5px);
        border-color: color-mix(in srgb, var(--card-accent) 78%, white);
        box-shadow: 0 20px 42px rgba(0,0,0,.32), 0 0 26px color-mix(in srgb, var(--card-accent) 18%, transparent), inset 0 1px rgba(255,255,255,.1);
    }

    .dashboard-stat-card:hover::before { opacity: 1; animation: card-shimmer .8s ease; }
    .dashboard-stat-card.violet { --card-accent: #a78bfa; }
    .dashboard-stat-card.cyan { --card-accent: #67d8e8; }
    .dashboard-stat-card.orange { --card-accent: #ffae70; }
    .dashboard-stat-card.green { --card-accent: #62dfae; }
    .dashboard-stat-card.pink { --card-accent: #f18fc5; }
    .dashboard-stat-card.blue { --card-accent: #78aaff; }

    .dashboard-stat-top, .dashboard-stat-label, .dashboard-stat-value, .dashboard-stat-foot { position: relative; z-index: 2; }
    .dashboard-stat-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: .9rem; }
    .dashboard-stat-icon {
        display: grid;
        width: 2.45rem;
        height: 2.45rem;
        place-items: center;
        border: 1px solid color-mix(in srgb, var(--card-accent) 35%, transparent);
        border-radius: 13px;
        background: color-mix(in srgb, var(--card-accent) 14%, transparent);
        font-size: 1.15rem;
    }
    .dashboard-stat-tag { color: color-mix(in srgb, var(--card-accent) 76%, white); font-size: .65rem; font-weight: 750; letter-spacing: .13em; }
    .dashboard-stat-label { color: #c9c9d7; font-size: .91rem; font-weight: 600; }
    .dashboard-stat-value { margin-top: .1rem; color: #faf9ff; font-size: clamp(1.65rem, 2.3vw, 2.35rem); font-weight: 750; letter-spacing: -.045em; line-height: 1.2; overflow-wrap: anywhere; }
    .dashboard-stat-foot { display: flex; align-items: center; gap: .42rem; margin-top: .55rem; color: #a9a9ba; font-size: .76rem; }
    .dashboard-stat-foot span { color: var(--card-accent); font-size: .7rem; }

    @media (max-width: 1050px) {
        .dashboard-card-grid.four { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 620px) {
        .dashboard-card-grid.four, .dashboard-card-grid.three, .dashboard-card-grid.two { grid-template-columns: 1fr; }
        .dashboard-stat-card { min-height: 142px; }
    }

    /* A gentle entrance when moving between Dashboard, Ask, and Data views. */
    div[data-testid="stTabs"] [role="tabpanel"] > div {
        animation: view-arrive .58s cubic-bezier(.2,.7,.25,1) both;
    }

    /* Dashboard charts and overview tables reveal with a small lift. */
    div[data-testid="stVegaLiteChart"],
    div[data-testid="stArrowVegaLiteChart"],
    div[data-testid="stPlotlyChart"],
    div[data-testid="stDataFrame"] {
        animation: soft-enter .68s ease both;
        transition: transform .22s ease, box-shadow .22s ease;
    }

    div[data-testid="stVegaLiteChart"]:hover,
    div[data-testid="stArrowVegaLiteChart"]:hover,
    div[data-testid="stPlotlyChart"]:hover,
    div[data-testid="stDataFrame"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(70, 60, 140, .16);
    }

    /* Ask input receives a soft highlight when the user is typing. */
    div[data-testid="stTextInput"] input {
        transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
    }

    div[data-testid="stTextInput"] input:focus {
        border-color: rgba(167, 139, 250, .9);
        box-shadow: 0 0 0 3px rgba(139, 92, 246, .18), 0 0 22px rgba(139, 92, 246, .13);
        transform: translateY(-1px);
    }

    div[data-testid="stButton"] button[kind="primary"] {
        transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
    }

    div[data-testid="stButton"] button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 9px 24px rgba(124, 91, 230, .3);
        filter: brightness(1.08);
    }

    div[data-testid="stAlert"],
    div[data-testid="stCode"] {
        animation: soft-enter .5s ease both;
    }

    div[data-testid="stSpinner"] {
        animation: result-glow 1.8s ease-in-out infinite;
        border-radius: 14px;
    }

    div[data-testid="stMetric"] {
        min-height: 128px;
        border-color: rgba(157, 117, 255, .34);
        background: linear-gradient(140deg, rgba(49, 54, 90, .64), rgba(57, 39, 41, .56));
        box-shadow: 0 14px 34px rgba(0, 0, 0, .18), inset 0 1px rgba(255,255,255,.04);
        animation: soft-enter .55s ease both;
        transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        border-color: rgba(180, 150, 255, .72);
        box-shadow: 0 18px 40px rgba(74, 60, 150, .22), inset 0 1px rgba(255,255,255,.08);
    }

    div[data-testid="stPopover"] > button {
        min-height: 46px;
        border: 1px solid rgba(167, 139, 250, .38);
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(46, 49, 76, .92), rgba(34, 37, 52, .92));
        box-shadow: 0 8px 22px rgba(0, 0, 0, .2);
        transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
    }

    div[data-testid="stPopover"] > button:hover {
        transform: translateY(-2px);
        border-color: rgba(196, 181, 253, .82);
        box-shadow: 0 12px 28px rgba(99, 73, 190, .22);
    }

    div[data-testid="stTabs"] button[role="tab"] {
        padding: .8rem 1.1rem;
        transition: color .18s ease, background .18s ease;
    }

    div[data-testid="stTabs"] button[role="tab"]:hover {
        background: rgba(139, 92, 246, .09);
    }

    .app-eyebrow {
        display: inline-flex;
        align-items: center;
        gap: .55rem;
        margin: .15rem 0 .25rem;
        color: #b9b4d6;
        font-size: .76rem;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .app-eyebrow-dot {
        width: .48rem;
        height: .48rem;
        border-radius: 50%;
        background: #53d6a6;
        box-shadow: 0 0 0 0 rgba(83, 214, 166, .62);
        animation: live-pulse 2.2s ease-out infinite;
    }

    @keyframes live-pulse {
        70% { box-shadow: 0 0 0 .55rem rgba(83, 214, 166, 0); }
        100% { box-shadow: 0 0 0 0 rgba(83, 214, 166, 0); }
    }

    @media (max-width: 850px) {
        .block-container {
            width: calc(100vw - 24px);
            padding-left: .75rem;
            padding-right: .75rem;
        }
        .stApp::before, .stApp::after { opacity: .14; }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: .01ms !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
            transition-duration: .01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# PAGE HEADER AND TOP-RIGHT MENUS
# ============================================================

feature_defaults = {
    "feature_schema_retrieval": True,
    "feature_value_retrieval": True,
    "feature_self_correction": True,
    "feature_safety_check": True,
    "feature_hybrid_bm25": True,
    "feature_abstention": True,
}
for feature_key, default_value in feature_defaults.items():
    # Keep the demo pipeline fully enabled for every run of the app.
    st.session_state[feature_key] = default_value

header_title, settings_col, profile_col = st.columns([8, 1, 1])
with header_title:
    st.markdown(
        '<div class="app-eyebrow"><span class="app-eyebrow-dot"></span>Live workspace · Enterprise analytics</div>',
        unsafe_allow_html=True,
    )
    st.title("Enterprise Data Dashboard")

with settings_col:
    with st.popover("⚙️ Settings"):
        st.subheader("Pipeline Settings")
        st.caption("All pipeline features are enabled for this demo.")
        schema_retrieval = st.toggle(
            "Schema Retrieval", key="feature_schema_retrieval", disabled=True
        )
        value_retrieval = st.toggle(
            "Value Retrieval", key="feature_value_retrieval", disabled=True
        )
        self_correction = st.toggle(
            "Self-Correction", key="feature_self_correction", disabled=True
        )
        safety_check = st.toggle(
            "SQL Safety", key="feature_safety_check", disabled=True
        )
        hybrid_bm25 = st.toggle(
            "Hybrid BM25", key="feature_hybrid_bm25", disabled=True
        )
        abstention = st.toggle(
            "Calibrated Abstention", key="feature_abstention", disabled=True
        )
        st.divider()
        st.success("Database connected")
        st.caption("AI-generated SQL is read-only. CRUD changes use Data Management.")

with profile_col:
    with st.popover("👤 Profile"):
        current_user = st.session_state.get("user", "")
        st.subheader("Profile")
        st.write(f"**{current_user}**")
        try:
            with sqlite3.connect("file:data/users.db?mode=ro", uri=True) as profile_conn:
                profile = profile_conn.execute(
                    "SELECT email, created_at FROM users WHERE username = ?",
                    (current_user,),
                ).fetchone()
            if profile:
                st.caption(profile[0])
                st.caption(f"Member since {profile[1]}")
        except sqlite3.Error:
            st.caption("Account details are unavailable.")
        if st.button("Log out", key="profile_logout", use_container_width=True):
            logout_user()
            st.rerun()

st.caption(
    "Live business overview, data management, and natural-language SQL."
)


# ============================================================
# CONFIG UPDATE
# ============================================================

CONFIG["use_schema_retrieval"] = (
    schema_retrieval
)

CONFIG["use_value_retrieval"] = (
    value_retrieval
)

CONFIG["use_self_correction"] = (
    self_correction
)

CONFIG["use_safety_check"] = (
    safety_check
)

CONFIG["use_hybrid_bm25"] = (
    hybrid_bm25
)

CONFIG["use_abstention"] = (
    abstention
)

CONFIG["verbose"] = False


# ============================================================
# DATABASE CONNECTION
# ============================================================

@st.cache_resource
def get_connection():

    return sqlite3.connect(
        DB,
        check_same_thread=False,
    )


conn = get_connection()


@st.cache_resource
def get_crud_connection():
    return sqlite3.connect(
        DB,
        check_same_thread=False,
    )


crud_conn = get_crud_connection()


dashboard_tab, ask_tab, data_tab = st.tabs(
    ["Dashboard", "Ask with AI", "Data Management"]
)


with dashboard_tab:
    st.header("Business Dashboard")
    st.caption("Live totals and trends from the current SQLite data.")

    customer_total = conn.execute("SELECT COUNT(*) FROM cust_mst").fetchone()[0]
    product_total = conn.execute("SELECT COUNT(*) FROM prod_mst").fetchone()[0]
    order_total = conn.execute("SELECT COUNT(*) FROM ord_txn").fetchone()[0]
    employee_total = conn.execute("SELECT COUNT(*) FROM emp_rec").fetchone()[0]
    revenue_total = conn.execute("SELECT COALESCE(SUM(amt), 0) FROM ord_txn").fetchone()[0]
    average_order = conn.execute("SELECT COALESCE(AVG(amt), 0) FROM ord_txn").fetchone()[0]
    delivered_total = conn.execute(
        "SELECT COUNT(*) FROM ord_txn WHERE stat_cd = 3"
    ).fetchone()[0]

    render_dashboard_cards(
        [
            ("👥", "Customers", f"{customer_total:,}", "Customer records", "violet"),
            ("📦", "Products", f"{product_total:,}", "Products in catalog", "cyan"),
            ("🧾", "Orders", f"{order_total:,}", "Orders in the database", "orange"),
            ("🧑‍💼", "Employees", f"{employee_total:,}", "Employee records", "green"),
        ],
        "four",
    )

    render_dashboard_cards(
        [
            ("↗️", "Total Order Revenue", f"₹{revenue_total:,.2f}", "Revenue across all orders", "pink"),
            ("◉", "Average Order Value", f"₹{average_order:,.2f}", "Average revenue per order", "blue"),
            ("✓", "Delivered Orders", f"{delivered_total:,}", "Successfully delivered", "green"),
        ],
        "three",
    )

    dashboard_tables = get_database_tables(conn)
    inventory_total = sum(
        conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}").fetchone()[0]
        for table_name in dashboard_tables
    )
    render_dashboard_cards(
        [
            ("▦", "Database Tables", f"{len(dashboard_tables):,}", "Tables in this database", "violet"),
            ("≋", "Records Across All Tables", f"{inventory_total:,}", "Rows across all tables", "cyan"),
        ],
        "two",
    )

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.subheader("Orders by Status")
        status_frame = pd.read_sql_query(
            "SELECT CASE stat_cd WHEN 1 THEN 'Pending' WHEN 2 THEN 'Processing' "
            "WHEN 3 THEN 'Delivered' WHEN 4 THEN 'Cancelled' ELSE 'Other' END AS status, "
            "COUNT(*) AS orders FROM ord_txn GROUP BY stat_cd ORDER BY stat_cd",
            conn,
        )
        if not status_frame.empty:
            st.bar_chart(status_frame.set_index("status"))
        else:
            st.info("No order data yet.")

    with chart_right:
        st.subheader("Monthly Order Revenue")
        monthly_frame = pd.read_sql_query(
            "SELECT substr(ord_dt,1,7) AS month, ROUND(SUM(amt),2) AS revenue "
            "FROM ord_txn GROUP BY substr(ord_dt,1,7) ORDER BY month",
            conn,
        )
        if not monthly_frame.empty:
            st.line_chart(monthly_frame.set_index("month"))
        else:
            st.info("No order data yet.")

    product_chart_col, state_chart_col = st.columns(2)
    with product_chart_col:
        st.subheader("Top Products by Revenue")
        product_revenue = pd.read_sql_query(
            "SELECT p.prod_nm AS product, ROUND(SUM(o.amt), 2) AS revenue "
            "FROM ord_txn o JOIN prod_mst p ON p.prod_id = o.prod_id "
            "GROUP BY p.prod_id, p.prod_nm ORDER BY revenue DESC LIMIT 10",
            conn,
        )
        if not product_revenue.empty:
            st.bar_chart(product_revenue.set_index("product"))
        else:
            st.info("Product sales will appear here when orders are available.")

    with state_chart_col:
        st.subheader("Orders by State")
        state_orders = pd.read_sql_query(
            "SELECT COALESCE(c.st_cd, 'Unknown') AS state, COUNT(*) AS orders "
            "FROM ord_txn o LEFT JOIN cust_mst c ON c.cust_id = o.cust_id "
            "GROUP BY state ORDER BY orders DESC LIMIT 10",
            conn,
        )
        if not state_orders.empty:
            st.bar_chart(state_orders.set_index("state"))
        else:
            st.info("Order distribution will appear here when orders are available.")

    category_chart_col, department_chart_col = st.columns(2)
    with category_chart_col:
        st.subheader("Revenue by Product Category")
        category_revenue = pd.read_sql_query(
            "SELECT COALESCE(p.cat_cd, 'Uncategorized') AS category, "
            "ROUND(SUM(o.amt), 2) AS revenue "
            "FROM ord_txn o JOIN prod_mst p ON p.prod_id = o.prod_id "
            "GROUP BY category ORDER BY revenue DESC",
            conn,
        )
        if not category_revenue.empty:
            st.bar_chart(category_revenue.set_index("category"))
        else:
            st.info("Category revenue will appear here when orders are available.")

    with department_chart_col:
        st.subheader("Employees by Department")
        department_employees = pd.read_sql_query(
            "SELECT COALESCE(dept_cd, 'Unassigned') AS department, COUNT(*) AS employees "
            "FROM emp_rec GROUP BY department ORDER BY employees DESC LIMIT 10",
            conn,
        )
        if not department_employees.empty:
            st.bar_chart(department_employees.set_index("department"))
        else:
            st.info("Department distribution will appear here when employees are available.")

    lower_left, lower_right = st.columns(2)
    with lower_left:
        st.subheader("Top Customers by Spend")
        top_customers = pd.read_sql_query(
            "SELECT c.cust_nm AS customer, ROUND(SUM(o.amt),2) AS spend "
            "FROM cust_mst c JOIN ord_txn o ON o.cust_id=c.cust_id "
            "GROUP BY c.cust_id,c.cust_nm ORDER BY spend DESC LIMIT 5",
            conn,
        )
        if not top_customers.empty:
            st.bar_chart(top_customers.set_index("customer"))
        else:
            st.info("No customer orders yet.")

    with lower_right:
        st.subheader("Recent Orders")
        recent_orders = pd.read_sql_query(
            "SELECT o.ord_id AS order_id,o.ord_dt AS date,c.cust_nm AS customer, "
            "p.prod_nm AS product,o.qty AS quantity,o.amt AS amount,o.stat_cd AS status_code "
            "FROM ord_txn o LEFT JOIN cust_mst c ON c.cust_id=o.cust_id "
            "LEFT JOIN prod_mst p ON p.prod_id=o.prod_id "
            "ORDER BY o.ord_dt DESC,o.ord_id DESC LIMIT 8",
            conn,
        )
        st.dataframe(recent_orders, use_container_width=True, hide_index=True)


with data_tab:
    st.markdown(
        "<span class='app-eyebrow'>DATA WORKSPACE · CRUD</span>",
        unsafe_allow_html=True,
    )
    st.title("Manage your data")
    st.caption("Browse business records, make changes, and keep your dashboard in sync.")

    friendly_names = {
        definition["table"]: name for name, definition in CRUD_TABLES.items()
    }
    friendly_names["usr_mst"] = "Users"
    crud_table_order = ["cust_mst", "prod_mst", "ord_txn", "emp_rec", "usr_mst"]
    existing_tables = set(get_database_tables(crud_conn))
    data_tables = [
        table_name for table_name in crud_table_order
        if table_name in existing_tables
    ]
    if st.session_state.get("crud_dataset_picker") not in data_tables:
        st.session_state["crud_dataset_picker"] = "cust_mst"
    selected_table = st.selectbox(
        "Choose a database table",
        data_tables,
        format_func=lambda table: f"{friendly_names.get(table, table)} · {table}",
        key="crud_dataset_picker",
    )
    selected_quoted = quote_identifier(selected_table)
    selected_count = crud_conn.execute(
        f"SELECT COUNT(*) FROM {selected_quoted}"
    ).fetchone()[0]
    selected_columns = crud_conn.execute(
        f"PRAGMA table_info({selected_quoted})"
    ).fetchall()
    total_rows = int(get_table_inventory(crud_conn)["Rows"].sum())
    summary_cols = st.columns(4)
    summary_cols[0].metric("CRUD tables", f"{len(data_tables):,}")
    summary_cols[1].metric("Records across database", f"{total_rows:,}")
    summary_cols[2].metric("Selected table records", f"{selected_count:,}")
    summary_cols[3].metric("Selected table columns", f"{len(selected_columns):,}")
    st.divider()
    if selected_table in CRUD_TABLES_BY_NAME:
        render_crud_table(
            crud_conn,
            friendly_names[selected_table],
            CRUD_TABLES_BY_NAME[selected_table],
        )
    else:
        render_generic_table(crud_conn, selected_table)


with ask_tab:


    if "question_input" not in st.session_state:

        st.session_state.question_input = ""

    # ============================================================
    # QUESTION
    # ============================================================

    question = st.text_input(
        "Ask a question about the enterprise database",
        key="question_input",
        placeholder=(
            "Example: How many delivered "
            "orders are there?"
        ),
    )


    # ============================================================
    # RUN BUTTON
    # ============================================================

    run_button = st.button(
        "Run Query",
        type="primary",
    )


    # ============================================================
    # RUN PIPELINE
    # ============================================================

    if run_button:

        if not question.strip():

            st.warning(
                "Please enter a question."
            )

        else:

            with st.spinner(
                "Checking the instant-answer cache or querying the database..."
            ):

                try:

                    cached_answer = get_demo_answer(question)

                    if cached_answer:
                        rows = cached_answer["rows"]
                        cols = cached_answer["columns"]
                        sql = cached_answer["sql"]
                        tokens = 0
                        trace = {
                            "source": "json_demo_cache",
                            "abstention": None,
                            "confidence_distance": None,
                            "retrieved_tables": [],
                            "retrieved_values": [],
                            "retries": 0,
                        }
                    else:
                        rows, cols, sql, tokens, trace = ask(
                            question,
                            conn,
                            return_trace=True,
                        )

                    # ====================================================
                    # ABSTENTION
                    # ====================================================

                    if sql == "ABSTAIN":

                        st.warning(
                            rows[0][0]
                            if rows
                            else (
                                "The system is not confident "
                                "enough to answer this question."
                            )
                        )

                    # ====================================================
                    # SUCCESS
                    # ====================================================

                    else:

                        if trace.get("source") == "json_demo_cache":
                            st.success(
                                "Optimized response returned from the question cache."
                            )
                        else:
                            st.success(
                                "Query completed successfully."
                            )

                        if CONFIG[
                            "use_safety_check"
                        ]:

                            st.info(
                                "🛡️ SQL safety validation enabled"
                            )

                        # ------------------------------------------------
                        # Metrics
                        # ------------------------------------------------

                        metric1, metric2 = st.columns(2)


                        metric1.metric(
                            "Rows Returned",
                            len(rows),
                        )


                        metric2.metric(
                            "Approx. Prompt Tokens",
                            tokens,
                        )


                        # ------------------------------------------------
                        # SQL
                        # ------------------------------------------------

                        st.subheader(
                            "Cached SQL"
                            if trace.get("source") == "json_demo_cache"
                            else "Generated SQL"
                        )

                        st.code(
                            sql,
                            language="sql",
                        )


                        # ------------------------------------------------
                        # RESULT
                        # ------------------------------------------------

                        st.subheader(
                            "Result"
                        )

                        if rows:
                            display_limit = 500
                            df = pd.DataFrame(rows[:display_limit], columns=cols)

                            if len(rows) > display_limit:
                                st.caption(
                                    f"Showing the first {display_limit:,} of {len(rows):,} rows "
                                    "to keep the page responsive."
                                )

                            st.dataframe(
                                df,
                                use_container_width=True,
                            )

                        else:

                            st.info(
                                "The query returned no rows."
                            )


                    # ====================================================
                    # AGENT TRACE
                    # ====================================================

                    st.divider()

                    with st.expander(
                        "Agent Trace",
                        expanded=False,
                    ):

                        # ------------------------------------------------
                        # Retrieval Confidence
                        # ------------------------------------------------

                        st.subheader(
                            "Retrieval Confidence"
                        )

                        if trace.get("source") == "json_demo_cache":
                            st.info(
                                "The question matched a prepared response, so the app skipped embedding retrieval and the LLM call. New questions continue through the full SQL generation pipeline."
                            )


                        confidence = trace.get(
                            "confidence_distance"
                        )


                        if confidence is not None:

                            st.metric(
                                "Embedding Distance",
                                f"{confidence:.3f}",
                            )

                            st.caption(
                                "Lower distance indicates "
                                "a stronger schema match."
                            )


                        # ------------------------------------------------
                        # Abstention Reason
                        # ------------------------------------------------

                        abstention_reason = trace.get(
                            "abstention"
                        )


                        if abstention_reason:

                            st.write(
                                abstention_reason
                            )


                        # ------------------------------------------------
                        # Retrieved Tables
                        # ------------------------------------------------

                        st.subheader(
                            "Retrieved Tables"
                        )


                        tables = trace.get(
                            "retrieved_tables",
                            [],
                        )


                        if tables:

                            for i, table in enumerate(
                                tables,
                                start=1,
                            ):

                                st.write(
                                    f"{i}. `{table}`"
                                )

                        else:

                            st.caption(
                                "No tables retrieved."
                            )


                        # ------------------------------------------------
                        # Retrieved Values
                        # ------------------------------------------------

                        st.subheader(
                            "Retrieved Database Values"
                        )


                        values = trace.get(
                            "retrieved_values",
                            [],
                        )


                        if values:

                            value_rows = []


                            for hit in values:

                                value_rows.append(
                                    {
                                        "Table": hit[
                                            "table"
                                        ],

                                        "Column": hit[
                                            "column"
                                        ],

                                        "Value": hit[
                                            "value"
                                        ],

                                        "Meaning": hit[
                                            "aliases"
                                        ],

                                        "Distance": round(
                                            hit[
                                                "distance"
                                            ],
                                            3,
                                        ),
                                    }
                                )


                            st.dataframe(
                                pd.DataFrame(
                                    value_rows
                                ),
                                use_container_width=True,
                            )

                        else:

                            st.caption(
                                "No value-level matches."
                            )


                        # ------------------------------------------------
                        # Execution Feedback
                        # ------------------------------------------------

                        st.subheader(
                            "Execution Feedback"
                        )


                        retries = trace.get(
                            "retries",
                            0,
                        )


                        if retries:

                            st.warning(
                                f"Self-correction retries: "
                                f"{retries}"
                            )

                        else:

                            st.success(
                                "No SQL correction was required."
                            )


                except Exception as e:

                    st.error(
                        f"Query failed: {e}"
                    )
