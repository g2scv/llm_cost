#!/bin/bash
# Deployment script for pricing tracker

set -e

echo "=== OpenRouter Pricing Tracker Deployment ==="

# Configuration
INSTALL_DIR="/opt/pricing-tracker"
SERVICE_USER="pricing-tracker"
VENV_DIR="$INSTALL_DIR/.venv"

# Create service user if doesn't exist
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    sudo useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
fi

# Create installation directory
echo "Creating installation directory: $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR/logs"

# Copy application files
echo "Copying application files..."
sudo cp -r ../app "$INSTALL_DIR/"
sudo cp -r ../configs "$INSTALL_DIR/"
sudo cp -r ../migrations "$INSTALL_DIR/"
sudo cp ../requirements.txt "$INSTALL_DIR/"

# Copy .env file if exists
if [ -f ../.env ]; then
    echo "Copying .env file..."
    sudo cp ../.env "$INSTALL_DIR/"
else
    echo "WARNING: No .env file found. Please create one at $INSTALL_DIR/.env"
fi

# Create virtual environment
echo "Creating virtual environment..."
sudo python3 -m venv "$VENV_DIR"

# Install dependencies
echo "Installing Python dependencies..."
sudo "$VENV_DIR/bin/pip" install --upgrade pip
sudo "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# Set ownership
echo "Setting file ownership..."
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
sudo chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true

# Install systemd service
echo "Installing systemd service..."
sudo cp systemd/pricing-tracker.service /etc/systemd/system/
sudo cp systemd/pricing-tracker.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start timer
echo "Enabling and starting timer..."
sudo systemctl enable pricing-tracker.timer
sudo systemctl start pricing-tracker.timer

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Service status:"
sudo systemctl status pricing-tracker.timer --no-pager
echo ""
echo "To view logs:"
echo "  sudo journalctl -u pricing-tracker.service -f"
echo ""
echo "To run manually:"
echo "  sudo systemctl start pricing-tracker.service"
