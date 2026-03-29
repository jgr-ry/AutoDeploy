# 🚀 AutoDeploy - Sistema de Despliegue Automatizado

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-green?style=flat-square&logo=flask)](https://flask.palletsprojects.com/)
[![GitHub](https://img.shields.io/badge/GitHub%20Webhook-Enabled-black?style=flat-square&logo=github)](https://docs.github.com/es/developers/webhooks-and-events/webhooks)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**Tu servidor merecía un despliegue automático. Ahora lo tiene.** ✨

[Características](#-características) • [Instalación](#-instalación) • [Configuración](#-configuración) • [Uso](#-uso)

</div>

---

## 📋 ¿Qué es AutoDeploy?

**AutoDeploy** es un servidor Python basado en Flask que actúa como webhook de GitHub. Cuando hagas push a tu repositorio, este sistema:

- ✅ **Detecta cambios** automáticamente en tu rama monitoreada
- 📡 **Descarga el código** ejecutando `git pull` en tu servidor
- ⚡ **Reinicia servicios** (PM2, Docker, etc.) sin intervención manual
- 💬 **Notifica a Discord** con detalles completos del despliegue
- 🔒 **Valida seguridad** con secretos HMAC-SHA256
- 🔄 **Reintentos inteligentes** ante fallos de conectividad
- 📊 **Panel de estado** HTML con dashboard visual

Es perfecto para automatizar deployments en **bots de Discord**, **servidores web**, **aplicaciones Node.js** y más.

---

## ⭐ Características

### 🎯 Despliegue Inteligente
- Escucha webhooks de GitHub en tiempo real
- Soporta repositorios públicos y privados (con GitHub Token)
- Reintentos automáticos (5 intentos por defecto)
- Buffer de Git optimizado para archivos grandes

### 🔒 Seguridad de Nivel Empresarial
- Validación de firma HMAC-SHA256 de GitHub
- Soporte para GitHub Personal Access Token (PAT)
- Solo ejecuta en rama específica seleccionada

### 💬 Notificaciones Detalladas a Discord
- Embeds visuales con código de colores
- Información del autor y commits
- Resumen de archivos (añadidos, modificados, eliminados)
- Logs de errores para debugging rápido
- Enlaces directos a GitHub

### 📊 Panel de Status
- Website HTML elegante responsive
- Indicador de estado en tiempo real
- Diseño estilo GitHub/Discord (oscuro)

### 🎨 Logs Coloreados
- Salida en consola con colores automáticos
- Información legible y organizada
- Oculta spam de HTTP para mayor claridad

---

## 🛠️ Requisitos

- **Python 3.7+**
- **Git** (instalado y configurado en tu servidor)
- **Cuenta de GitHub** (para webhooks)
- **Discord Webhook URL** (opcional, pero recomendado)
- Conexión a Internet en tu servidor

---

## 📥 Instalación

### 1️⃣ Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/AutoDeploy.git
cd AutoDeploy
```

### 2️⃣ Crear entorno virtual (recomendado)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Instalar dependencias
```bash
pip install flask requests colorama
```

---

## ⚙️ Configuración

Abre `autodeploy.py` y modifica estas variables al inicio del archivo:

```python
# Rama que se monitoreará
BRANCH_TO_MONITOR = 'refs/heads/main'

# Ruta absoluta del repositorio en tu servidor
DEPLOY_DIR = r'C:\ruta\a\tu\proyecto'  # Windows
# DEPLOY_DIR = '/home/usuario/proyecto'  # Linux

# Comando para reiniciar tu aplicación
RESTART_COMMAND = 'pm2 restart index'  # Para PM2
# RESTART_COMMAND = 'docker restart mi-contenedor'  # Para Docker

# Discord (obtener en https://discord.com/developers/applications)
DISCORD_WEBHOOK_URL = 'https://discordapp.com/api/webhooks/...'

# GitHub Secret (crear en ajustes del webhook)
GITHUB_SECRET = 'tu_secreto_super_seguro'

# Token Personal GitHub (para repositorios privados)
GITHUB_TOKEN = 'ghp_xxxxxxxxxxxxxxxxxxxx'

# Puerto donde escucha el webhook
PORT = 5000
```

### 📌 Dónde obtener tus tokens

**GitHub Webhook Secret:**
1. Ve a tu repositorio → ⚙️ Settings
2. Webhooks → Nuevo webhook → Payload URL: `http://tu-servidor:5000/webhook`
3. Content type: `application/json`
4. Genera un Secret fuerte
5. Selecciona eventos: "Just the push event"

**GitHub Personal Token (para privados):**
1. GitHub → Settings → Developer settings → Personal access tokens
2. Genera uno nuevo con permisos `repo` (read)
3. Cópialo en `GITHUB_TOKEN`

**Discord Webhook:**
1. Discord → Tu servidor → Ajustes del canal
2. Integraciones → Webhooks → Nuevo
3. Nombra "AutoDeploy" y copia la URL

---

## 🚀 Uso

### ▶️ Iniciar el servidor

```bash
python autodeploy.py
```

Verás un bonito ASCII art:
```
    ███████╗ ██████╗ ███████╗██████╗ ██╗      ██████╗ ██╗   ██╗
    ██╔════╝██╔═══██╗██╔════╝██╔══██╗██║     ██╔═══██╗╚██╗ ██╔╝
    █████╗  ██║   ██║█████╗  ██████╔╝██║     ██║   ██║ ╚████╔╝ 
    ██╔══╝  ██║   ██║██╔══╝  ██╔═══╝ ██║     ██║   ██║  ╚██╔╝  
    ███████╗╚██████╔╝███████╗██║     ███████╗╚██████╔╝   ██║   
```

### 🧪 Probar el webhook

```bash
# Hacer un push a tu rama monitoreada
git add .
git commit -m "Probando AutoDeploy"
git push origin main
```

Deberías ver en la consola:
```
2026-03-29 15:42:10 - [INFO] - NUEVO PUSH DETECTADO en la rama monitoreada: refs/heads/main
2026-03-29 15:42:10 - [INFO] - -> Repositorio: usuario/proyecto | Commit por John: Probando AutoDeploy
2026-03-29 15:42:11 - [INFO] - Git Pull exitoso
2026-03-29 15:42:12 - [INFO] - Reinicio exitoso
```

### 🌐 Ver panel de status

Visita: `http://tu-servidor:5000/`

Verás una página verde indicando que todo funciona correctamente.

---

## 📊 Flujo de Operación

```
┌─────────────────────────────────────────────────────────┐
│ 1. Haces PUSH a GitHub en rama monitoreada              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. GitHub envía webhook POST a tu servidor              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 3. AutoDeploy valida firma HMAC-SHA256                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 4. Ejecuta: git pull (con reintentos)                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Ejecuta comando de reinicio (PM2, Docker, etc)       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 6. Envía notificación bonita a Discord                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
    ✅ ¡Despliegue completado automáticamente!
```

---

## 🐛 Solución de Problemas

### ❌ "Error: Invalid signature"
```
✓ Verifica que GITHUB_SECRET coincida exactamente en GitHub y en el script
✓ Asegúrate de que el formato sea exacto (sin espacios)
```

### ❌ "Git pull failure: permission denied"
```
✓ Verifica permisos: chmod +x .git/hooks/*
✓ Comprueba que tienes acceso al repositorio remoto
✓ Si es privado, añade GITHUB_TOKEN
```

### ❌ "No module named 'flask'"
```bash
pip install flask requests colorama
```

### ❌ El webhook no se dispara
```
✓ Verifica que el puerto 5000 no esté bloqueado por firewall
✓ Comprueba que tu servidor tenga IP pública/DNS
✓ En GitHub, ve a Webhooks y mira los "Recent Deliveries"
```

### ❌ Discord no recibe notificaciones
```
✓ Valida que DISCORD_WEBHOOK_URL sea correcta
✓ Verifica permisos del webhook en Discord
✓ Mira los logs del script para ver errores exactos
```

---

## 📝 Ejemplos de Configuración

### 🤖 Para un Bot de Discord (PM2)
```python
DEPLOY_DIR = r'C:\bots\mi-bot'
RESTART_COMMAND = 'pm2 restart mi-bot'
PORT = 5000
```

### 🐳 Para Docker
```python
DEPLOY_DIR = '/home/app/proyecto'
RESTART_COMMAND = 'docker restart mi-app && docker restart nginx'
PORT = 5000
```

### 🌐 Para Node.js (systemd)
```python
DEPLOY_DIR = '/var/www/mi-app'
RESTART_COMMAND = 'systemctl restart mi-app'
PORT = 5000
```

---

## 🔐 Consejo de Seguridad

**Siempre usa:**
- ✅ `GITHUB_SECRET` con una cadena aleatoria fuerte
- ✅ Firewall: abre puerto 5000 solo a GitHub (IPs: 20.201.28.91, 20.205.243.166, etc)
- ✅ HTTPS en producción (usa Nginx con SSL)
- ✅ Token PAT con permisos mínimos (`repo` read-only)
- ✅ Monitorea los logs regularmente

---

## 📜 Licencia

MIT License - Ver [LICENSE](LICENSE) para más detalles

---

## 💡 Tips & Tricks

### 🔗 Detrás de un Reverse Proxy (Nginx)
```nginx
location /webhook {
    proxy_pass http://localhost:5000/webhook;
    proxy_http_version 1.1;
}
```

### 📱 Usar con Telegram en lugar de Discord
Modifica la función `send_discord_notification()` para enviar a Telegram Bot API.

### 🔄 Ejecutar en Background (systemd - Linux)
Crea `/etc/systemd/system/autodeploy.service`:
```ini
[Unit]
Description=AutoDeploy Webhook Service
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/AutoDeploy
ExecStart=/usr/bin/python3 /home/deploy/AutoDeploy/autodeploy.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Luego: `systemctl enable autodeploy && systemctl start autodeploy`

### 🟢 PM2 (Windows/Linux)
```bash
pm2 start autodeploy.py --name "autodeploy" --interpreter python3
pm2 save
pm2 startup
```

---

## 🤝 Contribuir

¿Encontraste un bug? ¿Tienes una idea? 

1. Fork el repo
2. Crea una rama (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## ❓ Preguntas Frecuentes

**P: ¿Funciona con GitHub Enterprise?**  
R: Sí, solo necesitas cambiar la URL del webhook.

**P: ¿Qué pasa si el git pull falla?**  
R: Reintenta automáticamente 5 veces con 10 segundos de espera entre intentos.

**P: ¿Puedo monitorear múltiples ramas?**  
R: Sí, duplica el código y cambia `BRANCH_TO_MONITOR`.

**P: ¿Necesito reiniciar manualmente después?**  
R: No, `RESTART_COMMAND` lo hace automáticamente.

---

<div align="center">

**Hecho con ❤️ por JGR**

⭐ Si te fue útil, ¡deja una estrella en GitHub!

</div>
