/*
 * PM2 ecosystem configuration for running the IPTV Elias stack without Docker.
 */

const path = require("path");

const projectRoot = path.resolve(__dirname);
const backendDir = path.join(projectRoot, "backend");
const pythonBin = path.join(backendDir, "venv", "bin", "python3");
const envFile = path.join(backendDir, ".env");

const backendLogsDir = "/var/log/iptv-backend";

module.exports = {
  apps: [
    {
      name: "iptv-backend",
      cwd: backendDir,
      script: pythonBin,
      args: ["-m", "app"],
      interpreter: "none",
      env_file: envFile,
      autorestart: true,
      watch: false,
      max_memory_restart: "512M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      out_file: path.join(backendLogsDir, "out.log"),
      error_file: path.join(backendLogsDir, "error.log"),
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    {
      name: "iptv-worker",
      cwd: backendDir,
      script: pythonBin,
      args: ["-m", "app.worker"],
      interpreter: "none",
      env_file: envFile,
      autorestart: true,
      watch: false,
      max_memory_restart: "512M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      out_file: path.join(backendLogsDir, "worker.out.log"),
      error_file: path.join(backendLogsDir, "worker.err.log"),
      merge_logs: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
  ],
};
