import json
import os
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "passengers.json")

CUPO_TOTAL = int(os.environ.get("CUPO_TOTAL", 40))
HORA_CIERRE = os.environ.get("HORA_CIERRE", "18:00")
MAIL_TO = os.environ.get("MAIL_TO", "marcelo.vasquez-externo@angloamerican.com")
TZ = ZoneInfo(os.environ.get("TZ_NAME", "America/Santiago"))
CRON_SECRET = os.environ.get("CRON_SECRET", "")

lock = threading.Lock()

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


def load_passengers():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_passengers(lst):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)


def ahora_local():
    return datetime.now(TZ)


def fecha_viaje():
    return (ahora_local().date() + timedelta(days=1)).isoformat()


def hora_cierre_parts():
    h, m = HORA_CIERRE.split(":")
    return int(h), int(m)


def inscripcion_abierta():
    h, m = hora_cierre_parts()
    ahora = ahora_local()
    cierre = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    return ahora < cierre


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/estado")
def estado():
    fecha = fecha_viaje()
    with lock:
        pasajeros = load_passengers()
    de_manana = [p for p in pasajeros if p["fecha"] == fecha]
    return jsonify(
        {
            "fechaViaje": fecha,
            "cupoTotal": CUPO_TOTAL,
            "cuposDisponibles": max(0, CUPO_TOTAL - len(de_manana)),
            "cerrado": not inscripcion_abierta(),
            "horaCierre": HORA_CIERRE,
            "pasajeros": de_manana,
        }
    )


@app.route("/api/inscribir", methods=["POST"])
def inscribir():
    data = request.get_json(force=True, silent=True) or {}
    nombre = (data.get("nombre") or "").strip()
    area = (data.get("area") or "").strip()

    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400

    if not inscripcion_abierta():
        return (
            jsonify(
                {
                    "error": f"Las inscripciones para mañana están cerradas (cierre diario {HORA_CIERRE} hs). "
                    "Vuelve a intentar después de medianoche para el siguiente viaje."
                }
            ),
            400,
        )

    fecha = fecha_viaje()
    with lock:
        pasajeros = load_passengers()
        de_manana = [p for p in pasajeros if p["fecha"] == fecha]

        if any(p["nombre"].strip().lower() == nombre.lower() for p in de_manana):
            return jsonify({"error": "Ya estás anotado/a en la lista de mañana"}), 400

        if len(de_manana) >= CUPO_TOTAL:
            return jsonify({"error": "No hay cupos disponibles para el viaje de mañana"}), 400

        nuevo = {
            "id": f"{int(time.time() * 1000)}-{len(pasajeros)}",
            "nombre": nombre,
            "area": area,
            "fecha": fecha,
            "creado": ahora_local().isoformat(timespec="seconds"),
            "enviado": False,
        }
        pasajeros.append(nuevo)
        save_passengers(pasajeros)

    return jsonify(nuevo), 201


@app.route("/api/inscribir/<pid>", methods=["DELETE"])
def cancelar(pid):
    fecha = fecha_viaje()
    with lock:
        pasajeros = load_passengers()
        objetivo = next((p for p in pasajeros if p["id"] == pid), None)

        if objetivo is None:
            return jsonify({"error": "No encontrado"}), 404
        if objetivo["fecha"] != fecha:
            return jsonify({"error": "Solo se puede cancelar la lista abierta actual"}), 400

        pasajeros = [p for p in pasajeros if p["id"] != pid]
        save_passengers(pasajeros)

    return jsonify({"ok": True})


def construir_html(fecha, pasajeros):
    if pasajeros:
        filas = "".join(
            f"<tr><td>{i + 1}</td><td>{p['nombre']}</td><td>{p.get('area', '')}</td></tr>"
            for i, p in enumerate(pasajeros)
        )
        tabla = (
            "<table border='1' cellpadding='6' cellspacing='0' "
            "style='border-collapse:collapse;font-family:sans-serif'>"
            "<tr><th>#</th><th>Nombre</th><th>Área</th></tr>" + filas + "</table>"
        )
    else:
        tabla = "<p>No hay pasajeros anotados para este viaje.</p>"

    return (
        f"<h3>Listado de pasajeros - Bus del {fecha}</h3>"
        f"<p>Total pasajeros: {len(pasajeros)} / {CUPO_TOTAL}</p>" + tabla
    )


def enviar_lista(fecha, pasajeros):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    mail_from = os.environ.get("MAIL_FROM", user)

    if not host or not user or not pwd:
        print(
            f"[AVISO] SMTP no configurado (revisa .env). No se envió el correo del "
            f"{fecha}. Pasajeros pendientes: {len(pasajeros)}"
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Listado de pasajeros bus - {fecha}"
    msg["From"] = mail_from
    msg["To"] = MAIL_TO
    msg.attach(MIMEText(construir_html(fecha, pasajeros), "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, pwd)
            server.sendmail(mail_from, [MAIL_TO], msg.as_string())
        print(f"[OK] Correo enviado a {MAIL_TO} con {len(pasajeros)} pasajeros ({fecha})")
        return True
    except Exception as e:
        print(f"[ERROR] Falló el envío de correo: {e}")
        return False


def proceso_envio_diario():
    fecha = fecha_viaje()
    with lock:
        pasajeros = load_passengers()
        de_manana = [p for p in pasajeros if p["fecha"] == fecha and not p["enviado"]]
        enviado_ok = enviar_lista(fecha, de_manana)
        if enviado_ok:
            for p in pasajeros:
                if p["fecha"] == fecha:
                    p["enviado"] = True
            save_passengers(pasajeros)


@app.route("/api/enviar-diario", methods=["POST"])
def enviar_diario():
    """Dispara el envío del listado diario. Pensado para un cron externo (ej. cron-job.org)
    que llama a esta ruta a las 18:00, además del hilo interno de respaldo."""
    if CRON_SECRET and request.args.get("token") != CRON_SECRET:
        return jsonify({"error": "No autorizado"}), 403
    proceso_envio_diario()
    return jsonify({"ok": True})


def scheduler_loop():
    h, m = hora_cierre_parts()
    ultimo_envio = None
    while True:
        ahora = ahora_local()
        if ahora.hour == h and ahora.minute == m and ultimo_envio != ahora.date():
            proceso_envio_diario()
            ultimo_envio = ahora.date()
        time.sleep(20)


threading.Thread(target=scheduler_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=False)
