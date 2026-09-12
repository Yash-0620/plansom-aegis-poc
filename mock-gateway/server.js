import express from 'express';
import pg from 'pg';

const { Pool } = pg;
const app = express();
app.use(express.json());

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://postgres:postgres@postgres-db:5432/plansom_db'
});

console.log('[Plansom Gateway] Initializing MCP Planning & Delegation Engine...');

// Unified MCP tool call endpoint
app.post('/mcp/v1/tools/call', async (req, res) => {
    const toolName = req.body.name || req.body.params?.name;
    const args = req.body.arguments || req.body.params?.arguments || {};

    if (toolName !== 'fetch_planning_data') {
        return res.status(404).json({ error: `Tool ${toolName} not supported` });
    }

    const { department, data_type } = args;

    if (!department || !data_type) {
        return res.status(400).json({ error: 'Missing mandatory parameters: department, data_type' });
    }

    // Native Microsoft Architecture: Prompt Shields cleared semantic intent.
    // Service credentials execute the mapped SQL query directly against PostgreSQL.
    try {
        let queryText = '';
        if (department === 'hr_department') {
            queryText = 'SELECT * FROM hr_planning_data;';
        } else if (department === 'executive_board') {
            queryText = 'SELECT * FROM executive_board_secrets;';
        } else {
            return res.status(400).json({ error: `Unknown department namespace: ${department}` });
        }

        console.log(`[Plansom Gateway] Entra ID Auth OK. Executing on DB: "${queryText}"`);
        const result = await pool.query(queryText);

        return res.status(200).json({
            status: 'success',
            department: department,
            recordCount: result.rowCount,
            records: result.rows
        });
    } catch (err) {
        console.error(`[Plansom Gateway] DB Query Error: ${err.message}`);
        return res.status(500).json({ error: err.message });
    }
});

app.listen(8000, '0.0.0.0', () => {
    console.log('[Plansom Gateway] Listening on 0.0.0.0:8000');
});