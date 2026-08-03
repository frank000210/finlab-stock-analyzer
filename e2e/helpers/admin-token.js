// @ts-check
const fs = require('fs')
const path = require('path')

function _loadSecret() {
  if (process.env.ADMIN_SECRET) return process.env.ADMIN_SECRET
  try {
    const env = fs.readFileSync(path.resolve(__dirname, '../../.env'), 'utf8')
    const m = env.match(/^ADMIN_SECRET=(.+)$/m)
    return m ? m[1].trim() : null
  } catch {
    return null
  }
}

/**
 * Returns an admin JWT for tests that call require_admin-protected endpoints.
 * Uses /api/v1/auth/direct-login with ADMIN_SECRET from env or repo .env file.
 *
 * @param {import('@playwright/test').APIRequestContext} request
 * @returns {Promise<string>} JWT token value (pass as X-Admin-Token header)
 */
async function getAdminToken(request) {
  const secret = _loadSecret()
  if (!secret) throw new Error('ADMIN_SECRET not found in env or .env file')
  const resp = await request.post('/api/v1/auth/direct-login', {
    data: { secret },
  })
  if (!resp.ok()) throw new Error(`direct-login failed: ${resp.status()}`)
  return (await resp.json()).token
}

module.exports = { getAdminToken }
