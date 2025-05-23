import os
import sys
import time
import json
import queue
import logging
import sqlite3
import datetime
import threading
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import uvicorn
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configuración de logging
log_folder = Path("logs")
log_folder.mkdir(exist_ok=True)

log_file = log_folder / "nic_checker.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("nic_checker")

# Configuración de la base de datos
DB_PATH = "nic_domains.db"

def init_db():
    """Inicializa la base de datos SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Crear tabla de dominios si no existe
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS domain_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            zone TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT,
            document_id TEXT,
            registration_date TEXT,
            expiration_date TEXT,
            check_date TIMESTAMP NOT NULL,
            UNIQUE(domain, zone)
        )
        ''')
        
        # Crear índice para búsquedas más rápidas
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_domain_zone ON domain_checks (domain, zone)')
        
        conn.commit()
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}")
    finally:
        conn.close()

def clean_old_logs():
    """Limpia los logs con más de 7 días de antigüedad."""
    try:
        current_time = time.time()
        seven_days_in_seconds = 7 * 24 * 60 * 60
        
        for log_file in log_folder.glob("*.log.*"):
            file_stat = os.stat(log_file)
            if (current_time - file_stat.st_mtime) > seven_days_in_seconds:
                os.remove(log_file)
                logger.info(f"Log antiguo eliminado: {log_file}")
    except Exception as e:
        logger.error(f"Error al limpiar logs antiguos: {e}")

@dataclass
class DomainInfo:
    domain: str
    zone: str
    status: str  # 'available' o 'registered'
    owner: Optional[str] = None
    document_id: Optional[str] = None
    registration_date: Optional[str] = None
    expiration_date: Optional[str] = None

class DomainResponse(BaseModel):
    domain: str
    zone: str
    status: str
    details: Dict[str, Any]
    check_date: str

# Cola global para procesar las solicitudes
request_queue = queue.Queue()

def check_domain(domain: str, zone: str) -> DomainInfo:
    """
    Verifica la disponibilidad de un dominio en NIC.ar.
    
    Args:
        domain: El nombre del dominio a verificar.
        zone: La zona del dominio (.com.ar, .ar, etc.)
        
    Returns:
        DomainInfo: Información sobre el dominio.
    """
    logger.info(f"Verificando dominio: {domain}{zone}")
    
    try:
        session = requests.Session()
        
        # Primero obtenemos la página principal para cookies y tokens
        main_url = "https://nic.ar/"
        response = session.get(main_url)
        response.raise_for_status()
        
        # Hacer POST al formulario de búsqueda
        url = "https://nic.ar/verificar-dominio"
        
        data = {
            "txtBuscar": domain,
            "cmbZonas": zone,
            "btn-consultar": "Buscar"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "https://nic.ar/"
        }
        
        response = session.post(url, data=data, headers=headers)
        response.raise_for_status()
        
        # Analizar la respuesta con BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        domain_info = DomainInfo(domain=domain, zone=zone, status="unknown")
        
        # Comprobar si el dominio está disponible
        available_div = soup.find("div", class_="si-dom-disponible")
        not_available_div = soup.find("div", class_="no-dom-disponible")
        
        if available_div:
            domain_info.status = "available"
            logger.info(f"Dominio {domain}{zone} está disponible")
        elif not_available_div:
            domain_info.status = "registered"
            logger.info(f"Dominio {domain}{zone} no está disponible")
            
            # Extraer información del propietario
            table = soup.find("table", class_="table")
            if table:
                rows = table.find_all("tr")
                
                for row in rows:
                    td = row.find("td")
                    if td:
                        text = td.text.strip()
                        
                        if "Nombre y Apellido:" in text:
                            domain_info.owner = text.replace("Nombre y Apellido:", "").strip()
                        elif "CUIT/CUIL/ID:" in text:
                            domain_info.document_id = text.replace("CUIT/CUIL/ID:", "").strip()
                        elif "Fecha de Alta:" in text:
                            domain_info.registration_date = text.replace("Fecha de Alta:", "").strip()
                        elif "Fecha de vencimiento:" in text:
                            domain_info.expiration_date = text.replace("Fecha de vencimiento:", "").strip()
        else:
            # Si no encontramos ninguno de los dos divs, podría haber un error
            logger.warning(f"No se pudo determinar si {domain}{zone} está disponible")
            raise Exception("No se pudo determinar si el dominio está disponible")
        
        return domain_info
        
    except requests.RequestException as e:
        logger.error(f"Error de solicitud HTTP: {e}")
        raise Exception(f"Error de conexión con NIC.ar: {e}")
    except Exception as e:
        logger.error(f"Error verificando dominio {domain}{zone}: {e}")
        raise Exception(f"Error verificando dominio: {e}")

def save_to_db(domain_info: DomainInfo):
    """Guarda o actualiza la información del dominio en la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        check_date = datetime.datetime.now().isoformat()
        
        # Intentar insertar, si ya existe actualizar
        cursor.execute('''
        INSERT INTO domain_checks 
        (domain, zone, status, owner, document_id, registration_date, expiration_date, check_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain, zone) 
        DO UPDATE SET 
            status = excluded.status,
            owner = excluded.owner,
            document_id = excluded.document_id,
            registration_date = excluded.registration_date,
            expiration_date = excluded.expiration_date,
            check_date = excluded.check_date
        ''', (
            domain_info.domain,
            domain_info.zone,
            domain_info.status,
            domain_info.owner,
            domain_info.document_id,
            domain_info.registration_date,
            domain_info.expiration_date,
            check_date
        ))
        
        conn.commit()
        logger.info(f"Información de {domain_info.domain}{domain_info.zone} guardada/actualizada en la base de datos")
    except Exception as e:
        logger.error(f"Error guardando en la base de datos: {e}")
    finally:
        conn.close()

def get_from_db(domain: str, zone: str) -> Optional[Dict[str, Any]]:
    """Obtiene la información del dominio desde la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM domain_checks
        WHERE domain = ? AND zone = ?
        ''', (domain, zone))
        
        result = cursor.fetchone()
        
        if result:
            return dict(result)
        return None
    except Exception as e:
        logger.error(f"Error obteniendo datos de la base de datos: {e}")
        return None
    finally:
        conn.close()

def process_queue_worker():
    """Procesa las solicitudes de la cola en segundo plano."""
    logger.info("Iniciando worker para procesar la cola de solicitudes")
    while True:
        try:
            task = request_queue.get()
            if task is None:  # Señal para terminar
                break
                
            domain, zone = task
            
            # Comprobar si ya tenemos una verificación reciente (menos de 1 hora)
            existing = get_from_db(domain, zone)
            if existing:
                check_date = datetime.datetime.fromisoformat(existing['check_date'])
                now = datetime.datetime.now()
                
                # Si la última verificación fue hace menos de 1 hora, solo actualizamos la fecha
                if (now - check_date).total_seconds() < 3600:
                    logger.info(f"Usando datos en caché para {domain}{zone}")
                    # Actualizar la fecha de verificación
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE domain_checks SET check_date = ? WHERE domain = ? AND zone = ?",
                        (now.isoformat(), domain, zone)
                    )
                    conn.commit()
                    conn.close()
                    request_queue.task_done()
                    continue
            
            # Si no tenemos datos recientes, verificamos con NIC.ar
            domain_info = check_domain(domain, zone)
            save_to_db(domain_info)
            
            request_queue.task_done()
        except Exception as e:
            logger.error(f"Error en el worker de la cola: {e}")
            if 'task' in locals():
                request_queue.task_done()

def queue_domain_check(domain: str, zone: str):
    """
    Encola una verificación de dominio para ser procesada en segundo plano.
    """
    request_queue.put((domain, zone))

def get_domain_history() -> List[Dict[str, Any]]:
    """Obtiene el historial completo de verificaciones de dominios."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM domain_checks ORDER BY check_date DESC LIMIT 100')
        
        results = [dict(row) for row in cursor.fetchall()]
        return results
    except Exception as e:
        logger.error(f"Error obteniendo historial de la base de datos: {e}")
        return []
    finally:
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    clean_old_logs()
    
    # Iniciar worker para procesar la cola
    worker = threading.Thread(target=process_queue_worker, daemon=True)
    worker.start()
    
    yield
    
    # Shutdown
    request_queue.put(None)  # Señal para terminar el worker

# Create FastAPI app
app = FastAPI(
    title="NIC.ar Domain Checker API",
    description="API para verificar la disponibilidad de dominios en NIC Argentina",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/check/{domain}")
async def check_domain_endpoint(
    domain: str, 
    zone: str = Query(None, description="Zona del dominio (opcional si ya está incluida en el dominio)"),
    background_tasks: BackgroundTasks = None
):
    """
    Verifica la disponibilidad de un dominio en NIC.ar.
    
    - **domain**: Nombre del dominio (puede incluir o no la zona)
    - **zone**: Zona del dominio (.com.ar, .ar, etc.) - opcional si ya está en domain
    
    Ejemplos:
    - /check/test?zone=.com.ar
    - /check/test.com.ar (detecta automáticamente la zona)
    - /check/google?zone=.ar
    """
    
    # Lista de zonas válidas
    valid_zones = [
        ".ar", ".com.ar", ".net.ar", ".gob.ar", ".int.ar", ".mil.ar", 
        ".musica.ar", ".org.ar", ".tur.ar", ".seg.ar", ".senasa.ar", 
        ".coop.ar", ".mutual.ar", ".bet.ar"
    ]
    
    # Si el dominio ya incluye una zona válida, extraerla
    domain_name = domain
    detected_zone = None
    
    for valid_zone in sorted(valid_zones, key=len, reverse=True):  # Ordenar por longitud para evitar conflictos
        if domain.endswith(valid_zone):
            domain_name = domain[:-len(valid_zone)]
            detected_zone = valid_zone
            break
    
    # Determinar qué zona usar
    if detected_zone and zone:
        # Si se detectó una zona en el dominio Y se pasó una zona como parámetro
        if detected_zone != zone:
            logger.warning(f"Zona detectada ({detected_zone}) difiere de la zona especificada ({zone}). Usando zona detectada.")
        final_zone = detected_zone
        final_domain = domain_name
    elif detected_zone:
        # Solo se detectó zona en el dominio
        final_zone = detected_zone
        final_domain = domain_name
    elif zone:
        # Solo se especificó zona como parámetro
        final_zone = zone
        final_domain = domain
    else:
        # No se especificó zona, usar .com.ar por defecto
        final_zone = ".com.ar"
        final_domain = domain
    
    # Validar formato del dominio final
    if not final_domain or len(final_domain) < 3:
        raise HTTPException(status_code=400, detail="El nombre del dominio debe tener al menos 3 caracteres")
    
    # Validar que la zona final sea válida
    if final_zone not in valid_zones:
        raise HTTPException(
            status_code=400, 
            detail=f"Zona inválida: {final_zone}. Zonas permitidas: {', '.join(valid_zones)}"
        )
    
    logger.info(f"Procesando solicitud: dominio='{final_domain}', zona='{final_zone}'")
    
    # Comprobar si ya tenemos datos en la base de datos
    db_result = get_from_db(final_domain, final_zone)
    
    # Si no hay datos o los datos tienen más de 1 hora, verificar en segundo plano
    if not db_result or (
        datetime.datetime.now() - datetime.datetime.fromisoformat(db_result['check_date'])
    ).total_seconds() > 3600:
        logger.info(f"Encolando verificación para {final_domain}{final_zone}")
        queue_domain_check(final_domain, final_zone)
    
    # Si no hay datos en la base de datos, verificar directamente
    if not db_result:
        try:
            # Verificar de manera síncrona
            domain_info = check_domain(final_domain, final_zone)
            save_to_db(domain_info)
            
            details = {}
            if domain_info.status == "registered":
                details = {
                    "owner": domain_info.owner,
                    "document_id": domain_info.document_id,
                    "registration_date": domain_info.registration_date,
                    "expiration_date": domain_info.expiration_date
                }
            
            check_date = datetime.datetime.now().isoformat()
            
            return DomainResponse(
                domain=final_domain,
                zone=final_zone,
                status=domain_info.status,
                details=details,
                check_date=check_date
            )
        except Exception as e:
            logger.error(f"Error verificando dominio {final_domain}{final_zone}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Devolver los datos que ya tenemos
        details = {}
        if db_result['status'] == "registered":
            details = {
                "owner": db_result['owner'],
                "document_id": db_result['document_id'],
                "registration_date": db_result['registration_date'],
                "expiration_date": db_result['expiration_date']
            }
        
        return DomainResponse(
            domain=db_result['domain'],
            zone=db_result['zone'],
            status=db_result['status'],
            details=details,
            check_date=db_result['check_date']
        )

@app.get("/history")
async def get_history():
    """Obtiene el historial completo de verificaciones de dominios."""
    results = get_domain_history()
    
    # Transformar los resultados en el formato adecuado
    formatted_results = []
    for result in results:
        details = {}
        if result['status'] == "registered":
            details = {
                "owner": result['owner'],
                "document_id": result['document_id'],
                "registration_date": result['registration_date'],
                "expiration_date": result['expiration_date']
            }
        
        formatted_results.append({
            "domain": result['domain'],
            "zone": result['zone'],
            "status": result['status'],
            "details": details,
            "check_date": result['check_date']
        })
    
    return formatted_results

@app.get("/")
async def root():
    """Endpoint raíz que devuelve información sobre la API."""
    return {
        "name": "NIC.ar Domain Checker API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/check/{domain}", "method": "GET", "description": "Verificar disponibilidad de un dominio"},
            {"path": "/history", "method": "GET", "description": "Obtener historial de verificaciones"}
        ]
    }

if __name__ == "__main__":
    uvicorn.run("nicar_domain_check:app", host="0.0.0.0", port=8000, reload=True)