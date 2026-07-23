#!/bin/bash
# Intern Tracker — one-time setup for any machine (macOS or Linux)
# Handles: Gmail credentials, Python deps, daily scheduling

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║    Summer 2027 Internship Tracker — Setup          ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Gmail App Password ────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]] && grep -q "GMAIL_APP_PASSWORD" "$ENV_FILE"; then
    echo "✅ .env already exists — skipping credentials step"
    echo "   (delete $ENV_FILE and re-run if you need to change password)"
else
    echo "STEP 1: Gmail App Password"
    echo "──────────────────────────"
    echo "You need a Gmail App Password (NOT your regular Gmail password)."
    echo ""
    echo "Get one here (takes 2 min):"
    echo "  https://myaccount.google.com/apppasswords"
    echo "  1. Sign in to your Google Account"
    echo "  2. Security → 2-Step Verification (must be ON first)"
    echo "  3. App passwords → Create → Name it 'Intern Tracker'"
    echo "  4. Copy the 16-character password (e.g. abcd efgh ijkl mnop)"
    echo ""
    read -rsp "Paste your Gmail App Password (input hidden): " APP_PASS
    echo ""

    if [[ -z "$APP_PASS" ]]; then
        echo "❌ No password entered. Aborting."
        exit 1
    fi

    read -rp "Gmail address to SEND from [3lokesharora@gmail.com]: " GMAIL_USER
    GMAIL_USER="${GMAIL_USER:-3lokesharora@gmail.com}"

    read -rp "Email address to RECEIVE updates [3lokesharora@gmail.com]: " RECIPIENT
    RECIPIENT="${RECIPIENT:-3lokesharora@gmail.com}"

    cat > "$ENV_FILE" <<EOF
GMAIL_USER=$GMAIL_USER
GMAIL_APP_PASSWORD=$APP_PASS
RECIPIENT_EMAIL=$RECIPIENT
EOF
    chmod 600 "$ENV_FILE"
    echo "✅ Saved to $ENV_FILE (chmod 600)"
fi

# Load env vars
set -a; source "$ENV_FILE"; set +a

# ── Step 2: Python deps ───────────────────────────────────────────────────────
echo ""
echo "STEP 2: Checking Python..."
python3 --version || { echo "❌ Python 3 not found. Install from https://python.org"; exit 1; }
echo "✅ Python OK"

# ── Step 3: Test email ────────────────────────────────────────────────────────
echo ""
echo "STEP 3: Sending test email to $RECIPIENT_EMAIL..."
python3 - <<PYEOF
import smtplib, os
from email.mime.text import MIMEText
user = os.environ['GMAIL_USER']
pwd  = os.environ['GMAIL_APP_PASSWORD']
to   = os.environ['RECIPIENT_EMAIL']
msg = MIMEText('<h3>Intern Tracker is configured!</h3><p>Daily updates will arrive each morning at 8 AM.</p>', 'html')
msg['Subject'] = '[Intern Tracker] Setup successful!'
msg['From']    = user
msg['To']      = to
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
    s.login(user, pwd)
    s.sendmail(user, to, msg.as_string())
print('✅ Test email sent to', to)
PYEOF

# ── Step 4: Schedule daily run ────────────────────────────────────────────────
echo ""
echo "STEP 4: Scheduling daily run at 8:00 AM..."

OS="$(uname -s)"

if [[ "$OS" == "Darwin" ]]; then
    # macOS — launchd
    PLIST_NAME="com.lokesh.interntracker"
    PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
    mkdir -p "$HOME/Library/LaunchAgents"

    # Inline the env vars so the job works even if .env path changes
    GMAIL_USER_VAL="$GMAIL_USER"
    GMAIL_PASS_VAL="$GMAIL_APP_PASSWORD"
    RECIPIENT_VAL="$RECIPIENT_EMAIL"

    cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>cd $SCRIPT_DIR && set -a && source .env && set +a && python3 tracker.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/tracker.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/tracker.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH"
    echo "✅ macOS launchd scheduled: daily 8:00 AM"
    echo "   Plist: $PLIST_PATH"

elif [[ "$OS" == "Linux" ]]; then
    # Linux — cron
    CRON_CMD="0 8 * * * cd $SCRIPT_DIR && set -a && source .env && set +a && python3 tracker.py >> $SCRIPT_DIR/tracker.log 2>&1"
    # Remove any old entry and add fresh one
    (crontab -l 2>/dev/null | grep -v "intern-tracker\|tracker.py"; echo "# intern-tracker"; echo "$CRON_CMD") | crontab -
    echo "✅ Linux cron scheduled: daily 8:00 AM"
    echo "   Check with: crontab -l"

else
    echo "⚠️  Unknown OS ($OS) — set up a daily scheduled task manually:"
    echo "   Command: cd $SCRIPT_DIR && set -a && source .env && set +a && python3 tracker.py"
fi

# ── Step 5: Run now ───────────────────────────────────────────────────────────
echo ""
read -rp "Run tracker NOW to get today's job list + resumes? [Y/n]: " RUN_NOW
RUN_NOW="${RUN_NOW:-Y}"
if [[ "$RUN_NOW" =~ ^[Yy] ]]; then
    echo ""
    echo "Running tracker (takes 3-5 min — scraping 164 companies)..."
    set -a; source "$ENV_FILE"; set +a
    python3 "$SCRIPT_DIR/tracker.py"
fi

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║  ✅ All done! Tracker is active.                   ║"
echo "║                                                    ║"
echo "║  📧 Daily email at 8 AM                            ║"
echo "║  📄 Resumes: intern-tracker/resumes/<date>/        ║"
echo "║  📋 Logs:    intern-tracker/tracker.log            ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Useful commands:"
echo "  Run manually:   cd $SCRIPT_DIR && python3 tracker.py"
echo "  View logs:      tail -f $SCRIPT_DIR/tracker.log"
if [[ "$OS" == "Darwin" ]]; then
echo "  Stop schedule:  launchctl unload ~/Library/LaunchAgents/com.lokesh.interntracker.plist"
echo "  Start schedule: launchctl load   ~/Library/LaunchAgents/com.lokesh.interntracker.plist"
elif [[ "$OS" == "Linux" ]]; then
echo "  Edit schedule:  crontab -e"
fi
