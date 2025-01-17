*Test Scenarios*

**1. Basic CSV Comparison (Exact Matches):**

*   **`products_1.csv`:**
    ```csv
    id,name,price
    1,Laptop,1200
    2,Mouse,25
    3,Keyboard,75
    4,Monitor,300
    ```

*   **`products_2.csv`:**
    ```csv
    product_id,product_name,cost
    1,Laptop,1200
    2,Mouse,25
    3,Keyboard,75
    ```

*   **Expected Results:**
    *   ID mapping: `id` -> `product_id`
    *   Name mapping: `name` -> `product_name`
    *   Price mapping: `price` -> `cost`
    *   Row unique to `products_2.csv`: `4,Monitor,300`

**2. JSONL Comparison (with Differences):**

*   **`users_1.jsonl`:**
    ```jsonl
    {"user_id": 1, "name": "Alice", "city": "New York"}
    {"user_id": 2, "name": "Bob", "city": "Los Angeles"}
    ```

*   **`users_2.jsonl`:**
    ```jsonl
    {"id": 2, "name": "Bob", "city": "San Francisco"}
    {"id": 3, "name": "Charlie", "city": "Chicago"}
    ```

*   **Expected Results:**
    *   ID mapping: `user_id` -> `id`
    *   Row unique to `users_1.jsonl`: `{"user_id": 1, "name": "Alice", "city": "New York"}`
    *   Row unique to `users_2.jsonl`: `{"id": 3, "name": "Charlie", "city": "Chicago"}`
    *   Row with differences (ID 2): `city` differs.

**3. CSV with 100+ Rows (Partial Matches, ID Detection):**

*   **`orders_1.csv`:** (105 rows)
    ```csv
    order_id,customer_name,product,quantity,order_date
    1001,John Doe,Laptop,1,2023-01-15
    1002,Jane Smith,Mouse,2,2023-01-15
    1003,Peter Jones,Keyboard,1,2023-01-16
    ... (102 more rows with varying data)
    ```

*   **`orders_2.csv`:** (103 rows)
    ```csv
    orderId,cust_name,product_name,qty,date
    1002,Jane Smith,Mouse,2,2023-01-15
    1003,Peter Jones,Keyboard,1,2023-01-16
    1004,Alice Brown,Monitor,1,2023-01-17
    ... (100 more rows with varying data)
    ```

*   **Expected Results:**
    *   Automatic ID detection: `order_id` -> `orderId`
    *   Mapping of other columns.
    *   Rows unique to each file (at least 2 in `orders_1.csv` and 1 in `orders_2.csv`).
    *   Rows with some data differences (quantity, date, etc.).

**4. Handling Missing/Null Values:**

*   **`data_1.csv`:**
    ```csv
    id,value
    1,10
    2,
    3,30
    ```

*   **`data_2.csv`:**
    ```csv
    id,value
    1,10
    2,20
    3,
    ```

*   **Expected Results:**
    *   ID 2: `data_1.csv` has a missing value, `data_2.csv` has 20.
    *   ID 3: `data_1.csv` has 30, `data_2.csv` has a missing value.

**6. Case insensitive matching (text values):**

*   **`case_1.csv`:**
    ```csv
    id,value
    1,hello
    2,WORLD
    3,Value
    ```

*   **`case_2.csv`:**
    ```csv
    id,value
    1,Hello
    2,world
    3,value
    ```

*   **Expected Results:** (with case-insensitive matching enabled)
    *   ID 1: values match
    *   ID 2: values match
    *   ID 3: values match

**7. CSV with different delimiters**
*   **`delim_1.csv`:**
    ```csv
    id;name;value
    1;Laptop;1200
    2;Mouse;25
    3;Keyboard;75
    ```

*   **`delim_2.csv`:**
    ```csv
    id,name,value
    1,Laptop,1200
    2,Mouse,25
    ```

*   **Expected Results:**
    *   ID mapping: `id` -> `id`
    *   Name mapping: `name` -> `name`
    *   Value mapping: `value` -> `value`
    *   Row unique to `delim_1.csv`: `3;Keyboard;75`

