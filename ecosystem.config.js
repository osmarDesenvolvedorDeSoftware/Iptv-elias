/*
 * PM2 ecosystem configuration for the IPTV Elias backend stack.
 * Each process runs from the Python virtualenv (./venv) without Docker.
 * Environment variables are loaded from the project .env file and logs are
 * persisted/rotated under /var/log/iptv-elias/.
 */

const path = require('path');

const baseDir = __dirname;
const backendDir = path.join(baseDir, 'backend');
const venvPath = path.join(baseDir, 'venv', 'bin');
const envFile = path.join(baseDir, '.env');
const logsDir = '/var/log/iptv-elias';

module.exports = {
  apps: [
    {
      name: 'backend-api',
      cwd: backendDir,
      script: path.join(venvPath, 'python'),
      args: ['-m', 'app'],
      env_file: envFile,
      out_file: path.join(logsDir, 'backend-api.log'),
      error_file: path.join(logsDir, 'backend-api.error.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      max_size: '200M',
      retain: 10,
      autorestart: true,
      watch: false,
    },
    {
      name: 'backend-worker',
      cwd: backendDir,
      script: path.join(venvPath, 'celery'),
      args: ['-A', 'app.extensions.celery_app', 'worker', '-l', 'info', '-Q', 'default'],
      env_file: envFile,
      out_file: path.join(logsDir, 'backend-worker.log'),
      error_file: path.join(logsDir, 'backend-worker.error.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      max_size: '200M',
      retain: 10,
      autorestart: true,
      watch: false,
    },
  ],
};
