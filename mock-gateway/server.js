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

// Azure APIM Content-Validation Schema for fetch_planning_data
const toolParamSchema = {
    type: "object",
    required: ["department", "data_type"],
    properties: {
        department: { 
            type: "string", 
            enum: ["hr_department", "executive_board"] 
        },
        data_type: { 
            type: "string", 
            enum: ["goals", "confidential_salaries"] 
        }
    },
    additionalProperties: false
};
const validateAPIMSchema = ajv.compile(toolParamSchema);

const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://postgres:postgres@postgres-db:5432/plansom_db'
});

// Helper: Query PostgreSQL and record downstream execution metrics
async function executeDatabaseQuery(correlation_id, agent_identity, department, data_type) {
    let queryText = '';
    
    if (department === 'hr_department') {
        queryText = 'SELECT * FROM hr_planning_data;';
    } else if (department === 'executive_board') {
        queryText = 'SELECT * FROM executive_board_secrets;';
    } else {
        throw new Error(`Target table unreachable for department: ${department}`);
    }

    // 1. Execute the actual query
    const result = await pool.query(queryText);
    
    // 2. Independently log the execution to the database audit table
    const auditQuery = `
        INSERT INTO database_audit_log 
        (correlation_id, agent_identity, tool_invoked, target_resource, execution_status, rows_returned) 
        VALUES ($1, $2, $3, $4, $5, $6)
    `;
    await pool.query(auditQuery, [
        correlation_id || 'req_unknown', 
        agent_identity || 'Unknown-Agent', 
        'fetch_planning_data', 
        department, 
        'EXECUTED', 
        result.rowCount
    ]);

    return {
        query: queryText,
        rowCount: result.rowCount,
        rows: result.rows
    };
}

// -----------------------------------------------------------------------------
// PATH A: MICROSOFT BASELINE (Azure APIM + Entra Agent ID)
// -----------------------------------------------------------------------------
app.post('/ms-baseline/mcp/v1/tools/call', async (req, res) => {
    const authHeader = req.headers['authorization'];
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({
            error: "Unauthorized: Missing or malformed Entra ID Bearer token"
        });
    }

    // 1. Authenticate Entra Agent ID JWT Claims
    const token = authHeader.split(' ')[1];
    let decoded;
    try {
        decoded = jwt.verify(token, ENTRA_SECRET);
    } catch (err) {
        return res.status(401).json({
            error: `Entra Token Validation Failed: ${err.message}`
        });
    }

    // Verify Agent has downstream database permissions
    const roles = decoded.roles || [];
    if (!roles.includes("Agent.Planning.Read")) {
        return res.status(403).json({
            error: "Forbidden: Agent lacks 'Agent.Planning.Read' app role"
        });
    }

    // 2. Azure APIM Content Validation (JSON Schema Check)
    const args = req.body.arguments || req.body.params?.arguments || {};
    const valid = validateAPIMSchema(args);
    if (!valid) {
        return res.status(400).json({
            error: "APIM Content-Validation Failure: Request body violates schema",
            validationErrors: validateAPIMSchema.errors
        });
    }

    // 3. Downstream Execution
    try {
        const correlationId = req.headers['x-correlation-id'] || `req_ms_${crypto.randomUUID().split('-')[0]}`;
        const agentIdentity = decoded.sub || "Unknown-Entra-Agent";
        
        const { department, data_type } = args;
        const dbResult = await executeDatabaseQuery(correlationId, agentIdentity, department, data_type);
        
        console.log(`[MS-Baseline APIM] PERMITTED -> Executed: "${dbResult.query}" | Rows Leaked: ${dbResult.rowCount}`);
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

// -----------------------------------------------------------------------------
// PATH B: UPSTREAM ENDPOINT (Protected by Aegis L7 Sidecar Proxy)
// -----------------------------------------------------------------------------
app.post('/mcp/v1/tools/call', async (req, res) => {
    const toolName = req.body.name || req.body.params?.name;
    const args = req.body.arguments || req.body.params?.arguments || {};

    if (toolName !== 'fetch_planning_data') {
        return res.status(404).json({ error: `Tool ${toolName} not supported` });
    }

    try {
        const correlationId = req.headers['x-correlation-id'] || `req_aegis_${crypto.randomUUID().split('-')[0]}`;
        const agentIdentity = req.headers['x-aegis-identity'] || "Aegis-Verified-Agent";

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