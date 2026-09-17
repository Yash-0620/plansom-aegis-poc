import express from 'express';
import pg from 'pg';
import jwt from 'jsonwebtoken';
import Ajv from 'ajv';
import crypto from 'crypto';

const { Pool } = pg;
const app = express();
app.use(express.json());

const ENTRA_SECRET = process.env.ENTRA_JWT_SECRET || "plansom-entra-agent-mock-secret-2026";
const ajv = new Ajv({ allErrors: true });

const toolParamSchema = {
    type: "object",
    required: ["department", "data_type"],
    properties: {
        department: { type: "string", enum: ["hr_department", "executive_board"] },
        data_type: { type: "string", enum: ["goals", "confidential_salaries"] }
    },
    additionalProperties: false
};
const validateAPIMSchema = ajv.compile(toolParamSchema);

// CHANGED: Fallback defaults to gateway_user explicitly ensuring NO BYPASS RLS
const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://gateway_user:gateway_pass@postgres-db:5432/plansom_db'
});

async function executeDatabaseQuery(correlation_id, agent_identity, department, data_type) {
    let queryText = '';
    if (department === 'hr_department') {
        queryText = 'SELECT * FROM hr_planning_data;';
    } else if (department === 'executive_board') {
        queryText = 'SELECT * FROM executive_board_secrets;';
    } else {
        throw new Error(`Target table unreachable for department: ${department}`);
    }

    const client = await pool.connect();
    try {
        await client.query('BEGIN');
        
        // Pass the identity securely into the PostgreSQL execution context for RLS
        await client.query(`SELECT set_config('app.agent_identity', $1, true);`, [agent_identity || 'Unknown-Agent']);
        
        // Query (RLS applies dynamically based on identity)
        const result = await client.query(queryText);
        
        // Independently log the execution to the database audit table
        const auditQuery = `
            INSERT INTO database_audit_log 
            (correlation_id, agent_identity, tool_invoked, target_resource, execution_status, rows_returned) 
            VALUES ($1, $2, $3, $4, $5, $6)
        `;
        await client.query(auditQuery, [
            correlation_id || 'req_unknown', 
            agent_identity || 'Unknown-Agent', 
            'fetch_planning_data', 
            department, 
            'EXECUTED', 
            result.rowCount
        ]);
        
        await client.query('COMMIT');
        return { query: queryText, rowCount: result.rowCount, rows: result.rows };
    } catch (error) {
        await client.query('ROLLBACK');
        throw error;
    } finally {
        client.release();
    }
}

// =========================================================================
// ADDED: INDEPENDENT AUDIT VERIFICATION ENDPOINT
// This allows the test harness to programmatically assert DB execution.
// =========================================================================
app.get('/sys/audit/:correlationId', async (req, res) => {
    const { correlationId } = req.params;
    try {
        const result = await pool.query('SELECT * FROM database_audit_log WHERE correlation_id = $1', [correlationId]);
        return res.status(200).json({ executions: result.rowCount, records: result.rows });
    } catch (err) {
        return res.status(500).json({ error: err.message });
    }
});

// -------------------------------------------------------------------------
// PATH A: MICROSOFT BASELINE (Azure APIM + Entra Agent ID)
// -------------------------------------------------------------------------
app.post('/ms-baseline/mcp/v1/tools/call', async (req, res) => {
    const toolName = req.body.name || req.body.params?.name;
    
    //Reject tools outside the allowed API scope
    if (toolName !== 'fetch_planning_data') {
        return res.status(404).json({ error: `Tool ${toolName} not supported` });
    }
    const authHeader = req.headers['authorization'];
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: "Missing or malformed Entra token" });
    }
    
    const token = authHeader.split(' ')[1];
    let decoded;
    try {
        decoded = jwt.verify(token, ENTRA_SECRET);
    } catch (err) {
        return res.status(401).json({ error: `Token Validation Failed: ${err.message}` });
    }

    const roles = decoded.roles || [];
    if (!roles.includes("Agent.Planning.Read")) {
        return res.status(403).json({ error: "Forbidden: Lacks Agent.Planning.Read role" });
    }

    const args = req.body.arguments || req.body.params?.arguments || {};
    if (!validateAPIMSchema(args)) {
        return res.status(400).json({ error: "APIM Validation Failure", validationErrors: validateAPIMSchema.errors });
    }

    try {
        const correlationId = req.headers['x-correlation-id'] || `req_ms_${crypto.randomUUID().split('-')[0]}`;
        const agentIdentity = decoded.sub || "Unknown-Entra-Agent";
        const { department, data_type } = args;
        
        const dbResult = await executeDatabaseQuery(correlationId, agentIdentity, department, data_type);
        console.log(`[MS-Baseline] PERMITTED -> Executed: "${dbResult.query}" | Rows Leaked: ${dbResult.rowCount}`);
        
        return res.status(200).json({
            status: "success",
            auth_layer: "Entra Agent ID + Azure APIM",
            caller: agentIdentity,
            executed_query: dbResult.query,
            records_returned: dbResult.rowCount,
            data: dbResult.rows
        });
    } catch (err) {
        return res.status(500).json({ error: err.message });
    }
});

// -------------------------------------------------------------------------
// PATH B: UPSTREAM ENDPOINT (Protected strictly by Aegis L7 Proxy)
// -------------------------------------------------------------------------
app.post('/mcp/v1/tools/call', async (req, res) => {
    const toolName = req.body.name || req.body.params?.name;
    const args = req.body.arguments || req.body.params?.arguments || {};
    
    if (toolName !== 'fetch_planning_data') {
        return res.status(404).json({ error: `Tool ${toolName} not supported` });
    }

    const agentIdentity = req.headers['x-aegis-identity'];
    if (!agentIdentity) {
        return res.status(401).json({ error: "Missing x-aegis-identity assertion from proxy" });
    }

    try {
        const correlationId = req.headers['x-correlation-id'] || `req_aegis_${crypto.randomUUID().split('-')[0]}`;
        const { department, data_type } = args;
        
        const dbResult = await executeDatabaseQuery(correlationId, agentIdentity, department, data_type);
        console.log(`[Aegis Upstream Gateway] Request processed via Aegis. Rows: ${dbResult.rowCount}`);
        
        return res.status(200).json({
            status: "success",
            auth_layer: "Aegis Invocation-Bound Proxy Verified",
            executed_query: dbResult.query,
            records_returned: dbResult.rowCount,
            data: dbResult.rows
        });
    } catch (err) {
        return res.status(500).json({ error: err.message });
    }
});

app.listen(8000, '0.0.0.0', () => {
    console.log('[Plansom Gateway v2.0] Listening on 0.0.0.0:8000');
});