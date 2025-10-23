/*
 * PM2 ecosystem configuration for running the IPTV Elias stack without Docker.
 */

const path = require('path');

const projectRoot = path.resolve(__dirname);
const backendDir = path.join(projectRoot, 'backend');
const frontendDir = path.join(projectRoot, 'ui');
const pythonBin = path.join(backendDir, 'venv', 'bin', 'python3');
const envFile = path.join(backendDir, '.env');

const backendLogsDir = '/var/log/iptv-backend';
const frontendLogsDir = '/var/log/iptv-ui';

module.exports = {
  apps: [
    {
      name: 'iptv-backend',
      cwd: backendDir,
      script: pythonBin,
      args: ['-m', 'app'],
      interpreter: 'none',
      env_file: envFile,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      out_file: path.join(backendLogsDir, 'backend.out.log'),
      error_file: path.join(backendLogsDir, 'backend.err.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
    {
      name: 'iptv-worker',
      cwd: backendDir,
      script: pythonBin,
      args: ['-m', 'app.worker'],
      interpreter: 'none',
      env_file: envFile,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      out_file: path.join(backendLogsDir, 'worker.out.log'),
      error_file: path.join(backendLogsDir, 'worker.err.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
    {
      name: 'iptv-frontend',
      cwd: frontendDir,
      script: 'npm',
      args: 'run dev',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'development',
      },
      out_file: path.join(frontendLogsDir, 'frontend.out.log'),
      error_file: path.join(frontendLogsDir, 'frontend.err.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
