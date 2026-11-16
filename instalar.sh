#!/bin/bash
# Instala a Coruja para o seu usuário (sem sudo).
#   bash instalar.sh               instala
#   bash instalar.sh --autostart   instala e abre a coruja junto com o computador
set -e
cd "$(dirname "$0")"

DEST="$HOME/.local/share/coruja"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"

if ! command -v python3 >/dev/null; then
  echo "Precisa do Python 3. Instale com o gerenciador de pacotes da sua distro."
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Precisa do Python 3.10 ou mais novo."
  exit 1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "Falta o módulo venv do Python. No Ubuntu/Debian: sudo apt install python3-venv"
  exit 1
fi

echo "Criando o ambiente da coruja..."
mkdir -p "$DEST"
if [ ! -x "$DEST/venv/bin/python" ]; then
  python3 -m venv "$DEST/venv"
fi
"$DEST/venv/bin/pip" install --quiet --upgrade pip
"$DEST/venv/bin/pip" install --quiet -r requirements.txt

echo "Copiando a coruja..."
rm -rf "$DEST/app"
mkdir -p "$DEST/app"
cp -r coruja "$DEST/app/"

mkdir -p "$BIN" "$APPS" "$ICONS"
cat > "$BIN/coruja" <<LAUNCHER
#!/bin/bash
cd "$DEST/app" && exec "$DEST/venv/bin/python" -m coruja "\$@"
LAUNCHER
chmod +x "$BIN/coruja"

echo "Desenhando o ícone..."
"$BIN/coruja" --export-icon "$ICONS/coruja.png" 256 || true

cat > "$APPS/coruja.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Coruja
Comment=Um amiguinho de mesa que mantém o computador acordado
Exec=$BIN/coruja
Icon=coruja
Terminal=false
Categories=Utility;
StartupWMClass=coruja
DESKTOP

if [ "$1" = "--autostart" ]; then
  mkdir -p "$HOME/.config/autostart"
  cp "$APPS/coruja.desktop" "$HOME/.config/autostart/coruja.desktop"
  echo "A coruja vai abrir junto com o computador."
fi

# O Qt 6 precisa da libxcb-cursor no X11/XWayland
if command -v ldconfig >/dev/null && ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor; then
  echo
  echo "Atenção: falta a biblioteca libxcb-cursor, que o Qt usa para abrir janelas."
  echo "  Ubuntu/Debian: sudo apt install libxcb-cursor0"
  echo "  Fedora:        sudo dnf install xcb-util-cursor"
  echo "  Arch:          sudo pacman -S xcb-util-cursor"
fi
if [ -n "$DISPLAY" ] && ! command -v xdotool >/dev/null; then
  echo
  echo "Dica: com o xdotool instalado, a coruja também evita que apps de chat marquem você como ausente."
fi

echo
echo "Pronto! Abra a Coruja pelo menu de aplicativos ou rode: coruja"
