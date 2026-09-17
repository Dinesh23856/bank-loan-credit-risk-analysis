# Future database agent

Planned endpoint: `POST /chat/sql`.

The production design must be read-only and admin-authorized, translate natural language into a validated query plan, use parameterized SQL, enforce a row limit, and reject INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE. No LLM provider is installed by this project until explicitly approved.
