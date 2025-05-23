# 🚀 GABE NICAR Checker

<div align="center">

![Python](https://img.shields.io/badge/python-v3.7+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**Una API moderna y robusta para verificar la disponibilidad de dominios .ar en tiempo real**

[Características](#-características) • [Instalación](#-instalación) • [Uso](#-uso) • [API](#-api-endpoints) • [Ejemplos](#-ejemplos)

</div>

---

## 📋 Descripción

**GABE NICAR Checker** es una API REST desarrollada en Python con FastAPI que permite verificar la disponibilidad de dominios argentinos (.ar) consultando directamente el registro oficial de NIC Argentina. 

La API incluye un sistema de caché inteligente, procesamiento en cola para múltiples solicitudes simultáneas, y un historial completo de consultas almacenado en SQLite.

## ✨ Características

- 🔍 **Verificación en tiempo real** de dominios .ar
- 🏪 **Cache inteligente** para reducir consultas redundantes
- 📊 **Base de datos SQLite** para historial de consultas
- 🔄 **Sistema de cola** para procesar múltiples solicitudes
- 📝 **Logging detallado** con rotación automática
- 🛡️ **Manejo robusto de errores**
- 🎯 **API REST** con documentación automática
- 🔧 **Detección automática** de zonas en dominios
- ⚡ **Alto rendimiento** con procesamiento asíncrono

## 🛠️ Tecnologías

- **FastAPI** - Framework web moderno y rápido
- **SQLite** - Base de datos para persistencia
- **BeautifulSoup** - Parser HTML para extraer información
- **Requests** - Cliente HTTP para consultas a NIC.ar
- **Uvicorn** - Servidor ASGI de alta performance

## 📦 Instalación

### Prerrequisitos

- Python 3.7 o superior
- pip (gestor de paquetes de Python)

### Pasos de instalación

1. **Clona el repositorio**
   ```bash
   git clone https://github.com/winnstorm/gabe-nicar-checker.git
   cd gabe-nicar-checker
   ```

2. **Instala las dependencias**
   ```bash
   pip install -r requirements.txt
   ```

3. **Ejecuta la aplicación**
   ```bash
   python nicar_domain_check.py
   ```

4. **¡Listo!** La API estará disponible en `http://localhost:8000`

## 🚀 Uso

### Inicio rápido

Una vez que la aplicación esté ejecutándose, puedes acceder a:

- **API**: `http://localhost:8000`
- **Documentación interactiva**: `http://localhost:8000/docs`
- **Documentación alternativa**: `http://localhost:8000/redoc`

### Verificación básica

```bash
# Verificar un dominio
curl http://localhost:8000/check/google.com.ar

# Verificar con zona específica
curl http://localhost:8000/check/test?zone=.ar
```

## 🌐 API Endpoints

### `GET /check/{domain}`

Verifica la disponibilidad de un dominio argentino.

**Parámetros:**
- `domain` (path): Nombre del dominio (puede incluir o no la zona)
- `zone` (query, opcional): Zona del dominio (.com.ar, .ar, etc.)

**Respuesta:**
```json
{
  "domain": "google",
  "zone": ".com.ar",
  "status": "registered|available",
  "details": {
    "owner": "Google LLC",
    "document_id": "123456789",
    "registration_date": "01/01/2000",
    "expiration_date": "01/01/2026"
  },
  "check_date": "2025-05-23T18:30:45.123456"
}
```

### `GET /history`

Obtiene el historial de consultas realizadas (últimas 100).

**Respuesta:**
```json
[
  {
    "domain": "test",
    "zone": ".com.ar",
    "status": "available",
    "details": {},
    "check_date": "2025-05-23T18:30:45.123456"
  }
]
```

### `GET /`

Información general de la API y endpoints disponibles.

## 💡 Ejemplos

### Diferentes formatos de consulta

```bash
# ✅ Dominio completo
curl http://localhost:8000/check/ejemplo.com.ar

# ✅ Dominio y zona separados
curl http://localhost:8000/check/ejemplo?zone=.com.ar

# ✅ Solo dominio (usa .com.ar por defecto)
curl http://localhost:8000/check/ejemplo

# ✅ Diferentes zonas
curl http://localhost:8000/check/gobierno?zone=.gob.ar
curl http://localhost:8000/check/organizacion?zone=.org.ar
```

### Respuesta para dominio disponible

```json
{
  "domain": "mi-startup-genial",
  "zone": ".com.ar",
  "status": "available",
  "details": {},
  "check_date": "2025-05-23T18:30:45.123456"
}
```

### Respuesta para dominio registrado

```json
{
  "domain": "google",
  "zone": ".com.ar",
  "status": "registered",
  "details": {
    "owner": "Google Argentina S.R.L.",
    "document_id": "30-123456789-0",
    "registration_date": "15/03/2001",
    "expiration_date": "15/03/2026"
  },
  "check_date": "2025-05-23T18:30:45.123456"
}
```

## 🗂️ Estructura del proyecto

```
gabe-nicar-checker/
├── nicar_domain_check.py    # Aplicación principal
├── requirements.txt         # Dependencias
├── README.md               # Documentación
├── logs/                   # Archivos de log
│   └── nic_checker.log
├── nic_domains.db          # Base de datos SQLite
└── test_domain_checker.py  # Tests unitarios
```

## ⚙️ Configuración

### Variables de entorno

La aplicación utiliza configuraciones por defecto, pero puedes personalizar:

- **Puerto**: Modifica en `nicar_domain_check.py` línea final
- **Host**: Cambia `0.0.0.0` por la IP deseada
- **Base de datos**: Modifica `DB_PATH` para cambiar ubicación

### Zonas soportadas

- `.ar` - Dominios generales argentinos
- `.com.ar` - Comerciales
- `.net.ar` - Proveedores de servicios de red
- `.org.ar` - Organizaciones
- `.gob.ar` - Gobierno
- `.mil.ar` - Militar
- `.int.ar` - Internacional
- `.tur.ar` - Turismo
- `.musica.ar` - Música
- `.coop.ar` - Cooperativas
- `.mutual.ar` - Mutuales
- `.bet.ar` - Apuestas
- `.seg.ar` - Seguros
- `.senasa.ar` - SENASA

## 📊 Características técnicas

### Sistema de caché

- Los resultados se almacenan en SQLite
- Cache válido por 1 hora
- Actualización automática en segundo plano

### Logging

- Logs rotativos cada 7 días
- Niveles: INFO, WARNING, ERROR
- Almacenados en `logs/nic_checker.log`

### Base de datos

```sql
CREATE TABLE domain_checks (
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
);
```

## 🧪 Tests

Ejecuta los tests unitarios:

```bash
python test_domain_checker.py
```

O con pytest:

```bash
pip install pytest
pytest test_domain_checker.py -v
```

## 🐳 Docker (Opcional)

```bash
# Construir imagen
docker build -t gabe-nicar-checker .

# Ejecutar contenedor
docker run -p 8000:8000 gabe-nicar-checker
```

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Changelog

### v1.0.0
- ✨ Verificación de dominios .ar
- 📊 Sistema de caché con SQLite
- 🔄 Procesamiento en cola
- 📝 Logging detallado
- 🎯 API REST completa

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## 🙏 Agradecimientos

- [NIC Argentina](https://nic.ar/) por proporcionar el servicio de consulta de dominios
- [FastAPI](https://fastapi.tiangolo.com/) por el excelente framework
- La comunidad de Python por las librerías utilizadas

---

<div align="center">

**¿Te gusta el proyecto? ¡Dale una ⭐ en GitHub!**

[Reportar Bug](https://github.com/winnstorm/gabe-nicar-checker/issues) • [Solicitar Feature](https://github.com/winnstorm/gabe-nicar-checker/issues) • [Wiki](https://github.com/winnstorm/gabe-nicar-checker/wiki)

</div>