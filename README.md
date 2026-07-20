# Bus de la empresa - Inscripción de pasajeros

App web simple para que los empleados se anoten en la lista de pasajeros del bus. Cada día a las 18:00 (configurable) se envía automáticamente el listado del viaje del día siguiente al correo de la empresa de transporte.

## Requisitos

- Python 3.9+

## Instalación

```bash
cd "app bus"
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` y completa:
- `MAIL_TO`: correo de la empresa de transporte (ya viene precargado).
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM`: datos de la cuenta de correo que enviará el listado.
  - Con Gmail: activa verificación en 2 pasos y genera una "contraseña de aplicación" en https://myaccount.google.com/apppasswords — usa esa contraseña, no la normal.
- `CUPO_TOTAL` (default 40) y `HORA_CIERRE` (default 18:00) si quieres cambiarlos.

## Ejecutar

```bash
python3 server.py
```

Abre http://localhost:5050 en el navegador.

> Nota: se usa el puerto 5050 porque en macOS el 5000 suele estar ocupado por "AirPlay Receiver".

## Cómo funciona

- Los empleados se anotan con nombre (y área opcional) para el viaje de **mañana**.
- El cupo diario es limitado (40 por defecto); al llenarse no se puede anotar más gente.
- Las inscripciones cierran todos los días a la hora configurada (18:00 por defecto); después de esa hora el formulario se bloquea hasta la medianoche, cuando se abre la inscripción para el siguiente viaje.
- Todos los días a la hora de cierre, la app envía automáticamente un correo con el listado de pasajeros a `MAIL_TO`.
- Los datos se guardan en `data/passengers.json` (se crea automáticamente).

## Probar el envío de correo sin esperar al horario de cierre

```bash
curl -X POST http://localhost:5050/api/enviar-diario
```

Revisa la consola del servidor para ver si el correo se envió correctamente o si falta configurar el SMTP.

## Desplegar en la nube (Render + cron-job.org)

Para que los empleados accedan desde cualquier dispositivo (celular, PC, cualquier red), la app se despliega en Render (gratis, sin tarjeta) y un servicio externo gratuito (cron-job.org) dispara el envío diario a las 18:00 en punto, sin depender de que Render esté "despierto" en ese momento.

### 1. Subir el código a GitHub

1. Crea una cuenta gratis en https://github.com (si no tienes).
2. Crea un repositorio nuevo (puede ser privado) desde https://github.com/new, por ejemplo `bus-owner`.
3. En esta carpeta, ejecuta (reemplaza la URL por la de tu repo):
   ```bash
   git init
   git add .
   git commit -m "Bus owner: app inicial"
   git branch -M main
   git remote add origin https://github.com/TU-USUARIO/bus-owner.git
   git push -u origin main
   ```

### 2. Crear el servicio en Render

1. Crea una cuenta gratis en https://render.com (puedes entrar directo con tu cuenta de GitHub).
2. Click en **New +** → **Web Service** → conecta el repositorio `bus-owner`.
3. Render detecta el `render.yaml` automáticamente (Build: `pip install -r requirements.txt`, Start: `gunicorn server:app --workers=1 --threads=4`). Si no lo detecta, complétalo manualmente con esos comandos.
4. En la sección **Environment**, completa las variables marcadas como secretas:
   - `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM` (tus datos de correo, ver sección de Gmail arriba).
   - `CRON_SECRET`: inventa una clave larga y random (ej. genera una con `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`). La vas a necesitar en el paso 3.
5. Click en **Deploy**. Cuando termine, Render te da una URL pública, ej: `https://bus-owner.onrender.com`.

### 3. Programar el envío diario con cron-job.org

1. Crea una cuenta gratis en https://cron-job.org.
2. Crea un nuevo cronjob:
   - URL: `https://TU-APP.onrender.com/api/enviar-diario?token=TU_CRON_SECRET`
   - Método: `POST`
   - Horario: todos los días a las 18:00, zona horaria `America/Santiago`.
3. Guarda. Este cronjob es el que garantiza el envío puntual aunque Render esté dormido por falta de uso.

### Notas sobre el plan gratuito de Render

- El servicio "duerme" tras ~15 minutos sin visitas y despierta solo (tarda unos segundos) cuando alguien entra o cuando cron-job.org lo llama.
- El archivo `data/passengers.json` persiste mientras el servicio no se vuelva a desplegar, pero **no está garantizado a largo plazo** en el plan free (no tiene disco persistente pagado). Para uso productivo serio a futuro, conviene sumar un disco persistente de Render (de pago) o una base de datos.
