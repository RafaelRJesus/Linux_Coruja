#!/bin/bash
# Remove a Coruja e as configurações dela.
pkill -f "python -m coruja" 2>/dev/null || true
rm -rf "$HOME/.local/share/coruja"
rm -f "$HOME/.local/bin/coruja" \
      "$HOME/.local/share/applications/coruja.desktop" \
      "$HOME/.local/share/icons/hicolor/256x256/apps/coruja.png" \
      "$HOME/.config/autostart/coruja.desktop"
rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/coruja"
echo "Coruja removida."
