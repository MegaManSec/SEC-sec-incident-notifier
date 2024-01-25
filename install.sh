#!/bin/bash
set -e

pip3 install feedparser beautifulsoup4 openai requests

# Step 1: Install sec-sec-incident-notifier.py
SEC_8K_EXECUTABLE="/usr/local/bin/sec-sec-incident-notifier.py"
cp sec-sec-incident-notifier.py "$SEC_8K_EXECUTABLE"
chmod +x "$SEC_8K_EXECUTABLE"
chown root:root $SEC_8K_EXECUTABLE

# Step 2: Create a service file and logrotate configuration for sec-sec-incident-notifier
SEC_8K_LOG_FILE="/var/log/sec-sec-incident-notifier.log"
SEC_8K_ERROR_LOG_FILE="/var/log/sec-sec-incident-notifier-error.log"
SEC_8K_SERVICE_FILE="/etc/systemd/system/sec-sec-incident-notifier.service"
SEC_8K_LOGROTATE_FILE="/etc/logrotate.d/sec-sec-incident-notifier"

cat <<EOL > $SEC_8K_SERVICE_FILE
[Unit]
Description=sec-sec-incident-notifier Service
After=network.target

[Service]
ExecStart=$SEC_8K_EXECUTABLE
Restart=always
DynamicUser=yes
Environment=OPENAI_KEY=$OPENAI_KEY
Environment=SLACK_WEBHOOK_URL=$SLACK_WEBHOOK
Environment="USER_AGENT=$USER_AGENT"
Environment=OPENAI_MAX_TOKENS=$OPENAI_MAX_TOKENS

StandardOutput=append:$SEC_8K_LOG_FILE
StandardError=append:$SEC_8K_ERROR_LOG_FILE

[Install]
WantedBy=default.target
EOL

cat <<EOL > $SEC_8K_LOGROTATE_FILE
$SEC_8K_LOG_FILE $SEC_8K_ERROR_LOG_FILE {
    monthly
    rotate 12
    compress
    missingok
    notifempty
    copytruncate
}
EOL

# Step 3: Reload systemd and start the sec-sec-incident-notifier service
systemctl daemon-reload
systemctl start sec-sec-incident-notifier

# Step 4: Enable the sec-sec-incident-notifier service to start at boot
systemctl enable sec-sec-incident-notifier

echo "sec-sec-incident-notifier has been installed in $SEC_8K_EXECUTABLE with OPENAI_KEY=$OPENAI_KEY, OPENAI_MAX_TOKENS=$OPENAI_MAX_TOKENS, SLACK_WEBHOOK_URL=$SLACK_WEBHOOK, and USER_AGENT=$USER_AGENT, and a service has been installed in $SEC_8K_SERVICE_FILE. The service is started and logging to $SEC_8K_LOG_FILE and $SEC_8K_ERROR_LOG_FILE, and log rotation is set up in $SEC_8K_LOGROTATE_FILE."
