import os
import subprocess
import requests
import logging
import hmac
import hashlib
import sys
import time
from flask import Flask, request, jsonify, send_from_directory
from colorama import init, Fore, Style

# Inicializar colorama para que los colores funcionen en Windows
init(autoreset=True)

# ==========================================
# CONFIGURACIÓN DEL SERVIDOR Y DESPLIEGUE
# ==========================================
# Rama que queremos observar (formato webhook de github, MAIN DEFAULT)
BRANCH_TO_MONITOR = 'refs/heads/main'  

# Cambiar por la ruta absoluta de tu repositorio en el servidor
DEPLOY_DIR = r'' 

# Comando para reiniciar servicios (ej: "pm2 restart index" o "docker restart mi_bot")
RESTART_COMMAND = 'echo "Reiniciando servicios..."' 

# Webhook de Discord
DISCORD_WEBHOOK_URL = ''

# Secreto de GitHub Webhook (déjalo vacío "" si no quieres usarlo, pero es muy recomendado)
GITHUB_SECRET = ''

# Token de Acceso Personal (PAT) de GitHub para clonar/pull de repositorios PRIVADOS.
# (déjalo vacío "" si el repositorio es público)
GITHUB_TOKEN = ''

# Puerto donde escuchará este script
PORT = 5000 
# ==========================================

class CustomFormatter(logging.Formatter):
    """Formateador de logs con colores para mejorar la estética en consola."""
    COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, Fore.WHITE)
        format_str = f"{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - [{log_color}%(levelname)s{Style.RESET_ALL}] - %(message)s"
        formatter = logging.Formatter(format_str, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

# Configuración del sistema de logs para la consola (CMD)
logger = logging.getLogger('AutoDeploy')
logger.setLevel(logging.INFO)
logger.propagate = False # Evita duplicidad si hay config global

if getattr(logger, 'handlers', None) is not None:
    logger.handlers.clear()

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

from werkzeug.serving import WSGIRequestHandler

# Ocultar los logs por defecto de HTTP GET de Flask para mayor limpieza
log_werkzeug = logging.getLogger('werkzeug')
log_werkzeug.setLevel(logging.ERROR)

# Silenciar por completo los mensajes de la clase base de http.server 
# para evitar que el spam de bots escaneando internet llene la consola de errores 400.
WSGIRequestHandler.log_error = lambda self, *args, **kwargs: None
WSGIRequestHandler.log_message = lambda self, *args, **kwargs: None
WSGIRequestHandler.log_request = lambda self, *args, **kwargs: None

app = Flask(__name__)

def verify_signature(payload_body, secret_token, signature_header):
    """Verifica que el payload viene realmente de GitHub usando el secret."""
    if not secret_token:
        return True # Si no hay secreto configurado, saltamos la validación
    
    if not signature_header:
        return False
        
    hash_object = hmac.new(secret_token.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)

def send_discord_notification(status, repo_name, branch, author_name, author_url, branch_url, commit_url, compare_url, commits_list, success=True, error_msg=""):
    """Envía un Embed a Discord indicando el resultado del despliegue con hipervínculos y listas de archivos."""
    import datetime

    # Colores Hexadecimales convertidos a Decimal para Discord
    color = 3066993 if success else 15158332 # Verde Esmeralda oscuro / Rojo Carmesí
    status_icon = "🟢" if success else "🔴"
    status_text = "Despliegue Exitoso" if success else "Error en el Despliegue"
    
    embed = {
        "title": f"{status_icon} Informe de {status_text}",
        "description": "El sistema ha detectado y procesado una nueva actualización en el repositorio.",
        "color": color,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), # Corrección del Warning
    }
    
    fields = [
        {
            "name": "📌 Repositorio", 
            "value": f"`{repo_name}`", 
            "inline": True
        },
        {
            "name": "🌿 Rama", 
            "value": f"[{branch}]({branch_url})", # Enlace Clickable
            "inline": True
        },
        {
            "name": "👤 Subido por", 
            "value": f"[{author_name}]({author_url})", # Enlace Clickable
            "inline": True
        }
    ]
    
    # Extraer arrays de archivos tocados de todos los commits nuevos y sumarizar
    added = []
    removed = []
    modified = []
    commits_msgs = []
    
    for c in commits_list:
        added.extend(c.get('added', []))
        removed.extend(c.get('removed', []))
        modified.extend(c.get('modified', []))
        commits_msgs.append(f"• {c.get('message', 'Sin mensaje de commit')}")
        
    # Limpiamos duplicados
    added = list(set(added))
    removed = list(set(removed))
    modified = list(set(modified))
    
    # Texto para Commits
    all_commits_str = "\n".join(commits_msgs)
    if len(all_commits_str) > 1000:
        texto_recortado = ""
        for index_char in range(1000):
            texto_recortado += all_commits_str[index_char]
            
        all_commits_str = f"{texto_recortado}\n... (Demasiados commits)"
        
    fields.append({
        "name": "📝 Mensajes de Commit", 
        "value": f"```\n{all_commits_str}\n```", 
        "inline": False
    })
    
    # Formatear lista de archivos
    files_str = ""
    if added:
        files_str += f"✅ **Añadidos:** {len(added)} archivo(s)\n"
    if removed:
        files_str += f"❌ **Eliminados:** {len(removed)} archivo(s)\n"
    if modified:
        files_str += f"🔄 **Modificados:** {len(modified)} archivo(s)\n"
        
    if not files_str:
        files_str = "No se detectaron cambios en archivos (forzado manual)."
        
    fields.append({
        "name": "📁 Resumen de Archivos", 
        "value": files_str, 
        "inline": False
    })

    # Si hubo error, adjuntamos la salida del log de error para poder depurar fácilmente
    if not success and error_msg:
        safe_error_msg = str(error_msg)
        error_field = {
            "name": "⚠️ Detalle del Error en Consola", 
            "value": f"```bash\n{safe_error_msg[-900:]}\n```", # Se recorta para no superar límite de Discord
            "inline": False
        }
        fields.append(error_field)

    fields.append({
        "name": "🔗 Enlaces Rápidos", 
        "value": f"• [Ver este Commit en GitHub]({commit_url})\n• [Ver Comparación de Cambios]({compare_url})", 
        "inline": False
    })
    
    embed = {
        "title": f"{status_icon} Informe de {status_text}",
        "description": "El sistema ha detectado y procesado una nueva actualización en el repositorio.",
        "color": color,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fields": fields,
        "footer": {
            "text": "JGR Autodeploy System",
            "icon_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" 
        }
    }
        
    payload = {
        "username": "JGR Deploy", 
        "avatar_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png", 
        "embeds": [embed]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
        logger.info("Notificación enviada a Discord exitosamente.")
    except Exception as e:
        logger.error(f"Error al intentar enviar webhook a Discord: {e}")


@app.route('/logo.png')
def serve_logo():
    """Ruta para servir el archivo logo.png."""
    # Enviar logo.png desde el directorio actual donde se esté ejecutando el script
    return send_from_directory('.', 'logo.png')

@app.route('/', methods=['GET'])
def index():
    """Ruta raíz que muestra el estado del autodeploy en HTML."""
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Autodeploy Status</title>
        <style>
            body {
                background-color: #0d1117; /* Fondo oscuro tipo GitHub/Discord */
                color: #c9d1d9;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                text-align: center;
                flex-direction: column;
            }
            .container {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 10px;
                padding: 40px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5);
                max-width: 500px;
            }
            .logo {
                width: 120px;
                height: auto;
                margin-bottom: 20px;
                border-radius: 10px;
                animation: pulse 2s infinite;
                object-fit: contain;
            }
            h1 {
                margin: 0 0 10px 0;
                font-size: 24px;
                color: #58a6ff;
            }
            p {
                margin: 0;
                color: #8b949e;
                font-size: 16px;
            }
            .status {
                margin-top: 25px;
                display: inline-block;
                padding: 8px 16px;
                background-color: rgba(35, 134, 54, 0.15);
                border: 1px solid rgba(86, 211, 100, 0.4);
                color: #3fb950;
                border-radius: 20px;
                font-weight: bold;
                font-size: 14px;
            }
            .status::before {
                content: '• ';
                color: #3fb950;
                font-size: 18px;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.05); }
                100% { transform: scale(1); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <img src="/logo.png" alt="Logo de JGR" class="logo" onerror="this.src='https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'; this.onerror=null;">
            <h1>Sistema de Autodeploys</h1>
            <p><strong>by JGR</strong></p>
            <div class="status">Funcionando Perfectamente</div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.route('/webhook', methods=['POST'])
def webhook():
    """Ruta (endpoint) que recibe el payload de GitHub."""
    # Verificación de seguridad usando GITHUB_SECRET
    if GITHUB_SECRET:
        signature = request.headers.get('X-Hub-Signature-256')
        if not verify_signature(request.data, GITHUB_SECRET, signature):
            logger.warning("Firma de Webhook de GitHub inválida o no proporcionada.")
            return jsonify({"status": "error", "message": "Invalid signature"}), 403

    data = request.json
    
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    # Verificar si es un evento de Push válido
    if 'ref' in data:
        branch = data['ref']
        
        if branch == BRANCH_TO_MONITOR:
            logger.info(f"NUEVO PUSH DETECTADO en la rama monitoreada: {branch}")
            
            # Extraer info del último commit para el log y Discord
            head_commit = data.get('head_commit', {})
            commit_msg = head_commit.get('message', 'Sin mensaje de commit')
            author = head_commit.get('author', {}).get('name', 'Usuario Desconocido')
            commit_url = head_commit.get('url', 'URL no disponible')
            branch_name = branch.replace('refs/heads/', '')
            
            repo_name = data.get('repository', {}).get('full_name', '')
            logger.info(f"-> Repositorio: {repo_name} | Commit por {author}: {commit_msg}")
            
            try:
                # 1. Moverse al directorio del proyecto
                os.chdir(DEPLOY_DIR)
                
                # Aumentar temporalmente el buffer de git para evitar el error RPC 500 u otros cortes de red (útil en archivos grandes como los de FiveM)
                subprocess.run(['git', 'config', 'http.postBuffer', '524288000'], check=False)
                
                # 2. Configurar la URL remota autenticada (sólo si GITHUB_TOKEN está configurado)
                logger.info("-> Iniciando proceso de actualización (git pull)...")
                
                pull_process = None
                max_retries = 5
                retry_delay = 10 # segundos entre intentos
                
                for attempt in range(1, max_retries + 1):
                    try:
                        logger.info(f"   [Intento {attempt}/{max_retries}] Ejecutando Git Pull...")
                        
                        if GITHUB_TOKEN and repo_name:
                            # Formato seguro: https://<TOKEN>@github.com/<USUARIO>/<REPO>.git
                            auth_url = f"https://{GITHUB_TOKEN}@github.com/{repo_name}.git"
                            
                            # Ejecutar Git Pull usando la URL autenticada
                            pull_process = subprocess.run(
                                ['git', 'pull', auth_url, branch_name],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                        else:
                            # Sin token, intentará usar las credenciales locales de la máquina
                            pull_process = subprocess.run(
                                ['git', 'pull', 'origin', branch_name],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                        
                        logger.info(f"Git Pull exitoso en intento {attempt}:")
                        print(format_git_output(pull_process.stdout))
                        break # Si tuvo éxito, salir del bucle
                        
                    except subprocess.CalledProcessError as e:
                        error_output = e.stderr if e.stderr else e.stdout
                        logger.warning(f"   [Error temporal en intento {attempt}]: {error_output.strip()}")
                        
                        if attempt == max_retries:
                            # Si es el último intento, volvemos a lanzar la excepción para que vaya al bloque de fallo general
                            logger.error(f"Fallo definitivo después de {max_retries} intentos.")
                            raise e 
                            
                        logger.info(f"   Esperando {retry_delay} segundos antes del próximo intento...")
                        time.sleep(retry_delay)
                        
                
                # 3. Reiniciar procesos (si está configurado)
                if RESTART_COMMAND:
                    logger.info(f"-> Ejecutando comando de reinicio: {RESTART_COMMAND}")
                    restart_process = subprocess.run(
                        RESTART_COMMAND,
                        shell=True,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    logger.info(f"Reinicio exitoso:\n{restart_process.stdout}")
                
                # Extraemos y preparamos todos los datos extendidos para el Discord Embed
                author_name = ""
                author_url = ""
                branch_url = f"https://github.com/{repo_name}/tree/{branch_name}"
                compare_url = data.get('compare', 'https://github.com')
                commit_url = "https://github.com"
                
                # Intentar sacar del sender si head_commit no lo tiene completo
                sender_data = data.get('sender', {})
                if 'login' in sender_data:
                    author_name = sender_data.get('login')
                    author_url = sender_data.get('html_url', f"https://github.com/{author_name}")
                
                # Lista de commits enviados en este push específico
                commits_list = data.get('commits', [])
                
                head_commit = data.get('head_commit')
                if head_commit:
                    commit_url = head_commit.get('url', commit_url)
                    if not author_name:
                        author_name = head_commit.get('author', {}).get('name', 'Desconocido')
                        author_url = f"https://github.com/{author_name}"

                send_discord_notification(
                    status="Exitoso",
                    repo_name=repo_name,
                    branch=branch_name,
                    author_name=author_name,
                    author_url=author_url,
                    branch_url=branch_url,
                    commit_url=commit_url,
                    compare_url=compare_url,
                    commits_list=commits_list,
                    success=True
                )
                
                return jsonify({"status": "success", "message": "Deploy completado"}), 200
                
            except subprocess.CalledProcessError as e:
                error_output = e.stderr if e.stderr else e.stdout
                logger.error(f"Error CRÍTICO durante el pull o reinicio: {error_output}")
                
                author_name = data.get('sender', {}).get('login', 'Desconocido')
                author_url = data.get('sender', {}).get('html_url', f"https://github.com/{author_name}")
                branch_url = f"https://github.com/{repo_name}/tree/{branch_name}"
                compare_url = data.get('compare', 'https://github.com')
                commits_list = data.get('commits', [])
                commit_url = data.get('head_commit', {}).get('url', 'https://github.com')
                
                # Notificar a Discord sobre el error en rojo
                send_discord_notification(
                    status="Fallido",
                    repo_name=repo_name,
                    branch=branch_name,
                    author_name=author_name,
                    author_url=author_url,
                    branch_url=branch_url,
                    commit_url=commit_url,
                    compare_url=compare_url,
                    commits_list=commits_list,
                    success=False,
                    error_msg=error_output
                )
                
                return jsonify({"status": "error", "message": "Falló el despliegue"}), 500
        else:
            logger.info(f"Push en rama inactiva '{branch}'. Solo monitoreamos '{BRANCH_TO_MONITOR}'. Se ignora.")
            return jsonify({"status": "ignored", "message": "Branch not monitored"}), 200
            
    # Si le hacen ping desde github por primera vez (evento ping)
    if 'zen' in data:
        logger.info("Ping de GitHub recibido correctamente. El Webhook está bien configurado.")
        return jsonify({"status": "success", "message": "Ping received"}), 200

    return jsonify({"status": "ignored", "message": "Evento no procesado"}), 200


def print_banner():
    """Imprime un banner agradable ASCII en la consola con la configuración actual."""
    banner = f"""
{Fore.CYAN}    █████╗ ██╗   ██╗████████╗ ██████╗ {Fore.GREEN}    ██████╗ ███████╗██████╗ ██╗      ██████╗ ██╗   ██╗
{Fore.CYAN}   ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗{Fore.GREEN}    ██╔══██╗██╔════╝██╔══██╗██║     ██╔═══██╗╚██╗ ██╔╝
{Fore.CYAN}   ███████║██║   ██║   ██║   ██║   ██║{Fore.GREEN}    ██║  ██║█████╗  ██████╔╝██║     ██║   ██║ ╚████╔╝ 
{Fore.CYAN}   ██╔══██║██║   ██║   ██║   ██║   ██║{Fore.GREEN}    ██║  ██║██╔══╝  ██╔═══╝ ██║     ██║   ██║  ╚██╔╝  
{Fore.CYAN}   ██║  ██║╚██████╔╝   ██║   ╚██████╔╝{Fore.GREEN}    ██████╔╝███████╗██║     ███████╗╚██████╔╝   ██║   
{Fore.CYAN}   ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ {Fore.GREEN}    ╚═════╝ ╚══════╝╚═╝     ╚══════╝ ╚═════╝    ╚═╝   
{Style.RESET_ALL}
    {Fore.MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}
                   {Fore.YELLOW}Sistema de Despliegue Automatizado (Webhook GitHub){Style.RESET_ALL}
                                   {Fore.WHITE}by JGR{Style.RESET_ALL}
    {Fore.MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}
"""
    print(banner)
    print(f"  {Fore.CYAN}📌 Rama monitoreada:{Style.RESET_ALL} {Fore.GREEN}{BRANCH_TO_MONITOR}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}📂 Directorio:{Style.RESET_ALL}       {Fore.GREEN}{DEPLOY_DIR}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}🎧 Webhook Port:{Style.RESET_ALL}     {Fore.GREEN}{PORT}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}🌐 Pagina estado:{Style.RESET_ALL}    {Fore.GREEN}http://localhost:{PORT}/{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}🔒 Modo de acceso:{Style.RESET_ALL}   {Fore.GREEN}{'Privado (Protegido con Token)' if GITHUB_TOKEN else 'Público'}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}🛡️ Secreto Webhook:{Style.RESET_ALL}  {Fore.GREEN}{'Activado' if GITHUB_SECRET else 'Desactivado (⚠ Inseguro)'}{Style.RESET_ALL}")
    print(f"\n{Fore.GREEN}[+] Esperando y escuchando peticiones entrantes desde GitHub...{Style.RESET_ALL}\n")

def format_git_output(git_output):
    """Parsea la salida cruda de git (como git pull) y la formatea con emojis y colores para consola."""
    if not git_output:
        return ""
    
    formatted_out = ""
    lines = str(git_output).strip().split('\n')
    
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
            
        # Resumen de archivos (e.g. "7 files changed, 521 deletions(-)")
        if "files changed" in stripped_line or "file changed" in stripped_line:
            formatted_out += f"\n{Fore.CYAN}📊 Resumen de la Actualización:{Style.RESET_ALL}\n"
            formatted_out += f"  {Fore.WHITE}└─ {stripped_line}{Style.RESET_ALL}\n"
        # Cuando git elimina un archivo desde delete mode
        elif stripped_line.startswith("delete mode"):
            try:
                # Normalmente es "delete mode 100644 filepath"
                parts = stripped_line.split(" ")
                filename = parts[-1] if len(parts) >= 4 else stripped_line.replace("delete mode ", "")
                formatted_out += f"  {Fore.RED}❌ Eliminado:{Style.RESET_ALL} {filename}\n"
            except Exception:
                formatted_out += f"  {Fore.RED}❌ Eliminado:{Style.RESET_ALL} {stripped_line}\n"
        # Creacion de archivos via git create mode
        elif stripped_line.startswith("create mode"):
            try:
                parts = stripped_line.split(" ")
                filename = parts[-1] if len(parts) >= 4 else stripped_line.replace("create mode ", "")
                formatted_out += f"  {Fore.GREEN}✅ Añadido:{Style.RESET_ALL} {filename}\n"
            except Exception:
                formatted_out += f"  {Fore.GREEN}✅ Añadido:{Style.RESET_ALL} {stripped_line}\n"
        # Archivos listados en diffstats ( e.g. " archivo.txt | 10 ++--" )
        elif "|" in stripped_line and ("+" in stripped_line or "-" in stripped_line):
            parts = stripped_line.split("|")
            filename = parts[0].strip()
            changes = parts[1].strip()
            
            if "+" in changes and "-" not in changes:
                color = Fore.GREEN
                icon = "✨ "
            elif "-" in changes and "+" not in changes:
                color = Fore.RED
                icon = "🗑️ "
            else:
                color = Fore.YELLOW
                icon = "🔄 "
            formatted_out += f"  {color}{icon}{filename}{Style.RESET_ALL} {Fore.LIGHTBLACK_EX}({changes}){Style.RESET_ALL}\n"
        # Para el git clean o pull generico informando update
        elif stripped_line.startswith("Removing"):
            formatted_out += f"  {Fore.RED}🗑️ Removed (Clean):{Style.RESET_ALL} {stripped_line.replace('Removing ', '')}\n"
        elif stripped_line.startswith("Updating"):
            formatted_out += f"\n{Fore.MAGENTA}🚀 {stripped_line}{Style.RESET_ALL}\n"
        elif stripped_line.startswith("HEAD is now at"):
            formatted_out += f"{Fore.BLUE}🎯 {stripped_line}{Style.RESET_ALL}\n"
        elif "Fast-forward" not in stripped_line:
            # Líneas restantes no catalogadas
            if stripped_line and not stripped_line.startswith("From https://"):
                # Mostrar en formato discreto
                pass

    if not formatted_out:
        return f"\n{Fore.WHITE}{git_output}{Style.RESET_ALL}\n"
        
    return formatted_out

def send_startup_discord_notification(is_sync_needed, details_msg=""):
    """Envía un Embed indicando que el script AutoDeploy acaba de encenderse."""
    import datetime
    
    color = 10181046 # Morado/Púrpura para anuncios del sistema
    
    if is_sync_needed:
        title = "🔄 Sistema AutoDeploy Iniciado (Sincronización Realizada)"
        desc = "El sistema se ha conectado, detectó actualizaciones pendientes y ha nivelado los archivos del servidor con GitHub exitosamente."
    else:
        title = "🟢 Sistema AutoDeploy Iniciado (Al Día)"
        desc = "El sistema de AutoDeploy by JGR está online y escuchando nuevas peticiones. El servidor local concuerda exactamente con GitHub."
        
    fields = [
        {
            "name": "📌 Repositorio Monitoreado", 
            "value": f"`{BRANCH_TO_MONITOR}`", 
            "inline": True
        },
        {
            "name": "📂 Directorio Local", 
            "value": f"`{DEPLOY_DIR}`", 
            "inline": True
        }
    ]
    
    if details_msg:
        fields.append({
            "name": "ℹ️ Detalles de Sincronización",
            "value": f"```bash\n{details_msg[-900:]}\n```",
            "inline": False
        })

    embed = {
        "title": title,
        "description": desc,
        "color": color,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "fields": fields,
        "footer": {
            "text": "JGR Autodeploy System - Log de Arranque",
            "icon_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
        }
    }
        
    payload = {
        "username": "JGR Deploy",
        "avatar_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
        "embeds": [embed]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        logger.error(f"Error enviando notificación de inicio a Discord: {e}")

def sync_on_startup():
    """Verifica si el repositorio local está sincronizado con el remoto al iniciar y fuerza la igualdad estricta."""
    branch_name = BRANCH_TO_MONITOR.replace('refs/heads/', '')
    logger.info(f"{Fore.YELLOW}[Sincronización Inicial]{Style.RESET_ALL} Verificando y forzando igualdad con la rama '{branch_name}' de GitHub...")
    try:
        os.chdir(DEPLOY_DIR)
        
        # Aumentamos buffer para no fallar en el fetch
        subprocess.run(['git', 'config', 'http.postBuffer', '524288000'], check=False)
        
        # Primero configuramos la forma de la url autenticada si usamos TOKEN para repositorios privados
        auth_url = 'origin'
        if GITHUB_TOKEN:
            # Obtener url del origin
            remote_url_check = subprocess.run(['git', 'config', '--get', 'remote.origin.url'], capture_output=True, text=True)
            if 'github.com' in remote_url_check.stdout:
                # Extraemos usuario y repo (muy simplificado, funciona comúnmente en formato https)
                auth_url = f"https://{GITHUB_TOKEN}@github.com/" + remote_url_check.stdout.split('github.com/')[-1].strip()

        # Descargamos el último estado oficial remoto
        logger.info(f" -> Ejecutando 'git fetch' para descargar historial remoto oficial...")
        remote_target = auth_url if GITHUB_TOKEN else 'origin'
        subprocess.run(['git', 'fetch', remote_target, branch_name], capture_output=True, text=True, check=True)
        
        # Para saber si necesitábamos sincronizar
        status_check = subprocess.run(['git', 'status', '-uno'], capture_output=True, text=True, check=True)
        is_sync_needed = "Your branch is behind" in status_check.stdout or "Tu rama está detrás de" in status_check.stdout
        
        # Forzamos al servidor local a ser un espejo exacto de GitHub (borrando cambios locales)
        logger.info(f" -> Forzando reinicio estricto local a origin/{branch_name}...")
        reset_process = subprocess.run(['git', 'reset', '--hard', f'FETCH_HEAD'], capture_output=True, text=True, check=True)
        
        # Limpiamos basura intrusa y archivos no rastreados que no estén en github
        clean_process = subprocess.run(['git', 'clean', '-fd'], capture_output=True, text=True, check=True)
        
        logger.info(f"{Fore.GREEN}¡Sincronización inicial estricta completada! Servidor = GitHub al 100%.{Style.RESET_ALL}")
        
        details = ""
        if is_sync_needed:
            logger.info(f"{Fore.MAGENTA}[!] Se aplicaron actualizaciones que estaban pendientes en GitHub.{Style.RESET_ALL}")
            print(format_git_output(reset_process.stdout + "\n" + clean_process.stdout))
            
            details = f"Reset Log:\n{reset_process.stdout.strip()}"
            if clean_process.stdout:
                details += f"\nClean Log:\n{clean_process.stdout.strip()}"
        else:
            logger.info(f"{Fore.GREEN}Todo correcto. Tu repositorio local está al día con GitHub.{Style.RESET_ALL}")
            
        send_startup_discord_notification(is_sync_needed, details_msg=details)

    except subprocess.CalledProcessError as e:
        error_output = e.stderr if e.stderr else e.stdout
        logger.error(f"{Fore.RED}[Error en Sincronización Inicial]: {error_output}{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"{Fore.RED}[Error en sistema local]: Verifica la ruta de DEPLOY_DIR. Error: {e}{Style.RESET_ALL}")

if __name__ == '__main__':
    print_banner()
    sync_on_startup()
    logger.info("Iniciando servicio HTTP Flask ocultando logs innecesarios para mantener la consola limpia.")
    
    # Ejecutamos Flask. host='0.0.0.0' expone la app para recibir peticiones externas
    app.run(host='0.0.0.0', port=PORT)
