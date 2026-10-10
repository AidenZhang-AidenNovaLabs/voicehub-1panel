const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');

const file = path.resolve('.data/.jwt-secret');
fs.mkdirSync(path.dirname(file), { recursive: true });
if (!fs.existsSync(file)) {
    const temporary = `${file}.${crypto.randomBytes(8).toString('hex')}`;
    try {
        fs.writeFileSync(temporary, crypto.randomBytes(64).toString('hex'), { flag: 'wx', mode: 0o600 });
        // Link a complete file exclusively so parallel starts cannot overwrite the winning key.
        try {
            fs.linkSync(temporary, file);
        } catch (error) {
            if (error.code !== 'EEXIST') throw error;
        }
    } finally {
        if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    }
}
if (!fs.lstatSync(file).isFile()) throw new Error('JWT secret must be a regular file');
const secret = fs.readFileSync(file, 'utf8');
if (Buffer.byteLength(secret) < 32 || /[\r\n\0]/.test(secret)) {
    throw new Error('Stored JWT secret is invalid; refusing to replace it');
}
fs.chmodSync(file, 0o600);
process.stdout.write(secret);
