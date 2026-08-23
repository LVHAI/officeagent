---
name: crm
description: CRM customer analysis and PostgreSQL access through the Database MCP sql_query tool.
---

# CRM Customer Analysis

Use the **Database MCP Server** to inspect CRM customer data stored in PostgreSQL.
This is a **domain-specific CRM skill**. When a request is clearly about customers,
customer value, purchase history, or churn, this skill takes precedence over the
generic SQL skill.

## Responsibilities

Use this skill when the user asks about:

- customer profiles
- customer regions or customer segments
- customer value / total spending
- purchase history and order counts
- recent purchases
- inactive or potential churn customers
- customer comparisons or rankings

## Data source

- PostgreSQL database: `officeagent`
- Primary table: `customers`
- Purchase table: `customer_orders`
- Database access: **Database MCP Server**
- SQL tool: `sql_query`

## Skill priority

- Treat this skill as the domain-specific workflow for CRM requests.
- Prefer this skill over the generic `Database SQL` skill when the request is about CRM customers.
- The generic SQL skill provides database-querying guidance; it must not replace the CRM workflow for a clearly CRM-specific request.
- CRM data access is centralized through the Database MCP `sql_query` tool.
- Do not call a separate CRM/customer tool when the required CRM information can be obtained from PostgreSQL through `sql_query`, unless the system explicitly requires that tool.

## Tool policy

- Discover Database MCP tools before invocation.
- Use the `sql_query` tool for PostgreSQL reads; do not fabricate CRM data.
- Discover or verify the database schema before constructing unfamiliar CRM queries.
- Only execute read-only `SELECT` / `WITH` queries.
- Prefer bounded queries with `customer_id`, `region`, date ranges, `LIMIT`, or other selective filters.
- Never modify schema or data through the CRM skill.
- Never invent table names or column names. Use the schema below or discovered schema metadata.
- Preserve source metadata from the Database MCP result, including the database, tool name, SQL used, and returned columns when available.
- If the requested information is not present in PostgreSQL, state that it is unavailable instead of guessing.

## Schema guidance

### customers

- `customer_id`: unique customer identifier
- `name`: customer name
- `email`: customer email
- `region`: customer region
- `level`: standard / silver / gold / platinum
- `total_spent`: accumulated customer spending
- `last_purchase_at`: most recent purchase time
- `created_at`: customer creation time

### customer_orders

- `order_id`: unique order identifier
- `customer_id`: customer identifier
- `order_amount`: order amount
- `order_status`: paid / cancelled / refunded
- `ordered_at`: order time

## Query examples

For the top customers in a region:

```sql
SELECT customer_id, name, region, level, total_spent, last_purchase_at
FROM customers
WHERE region = 'East China'
ORDER BY total_spent DESC
LIMIT 5;
```

For recent purchase history:

```sql
SELECT c.customer_id, c.name, o.order_id, o.order_amount, o.order_status, o.ordered_at
FROM customers c
JOIN customer_orders o ON o.customer_id = c.customer_id
WHERE c.customer_id = 'C001'
  AND o.ordered_at >= NOW() - INTERVAL '90 days'
ORDER BY o.ordered_at DESC
LIMIT 20;
```

For potential churn signals:

```sql
SELECT customer_id, name, region, level, total_spent, last_purchase_at
FROM customers
WHERE last_purchase_at < NOW() - INTERVAL '90 days'
ORDER BY total_spent DESC
LIMIT 50;
```
