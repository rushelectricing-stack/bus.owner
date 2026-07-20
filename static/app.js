const form = document.getElementById("form-inscripcion");
const nombreInput = document.getElementById("nombre");
const areaInput = document.getElementById("area");
const btnAnotarme = document.getElementById("btn-anotarme");
const errorMsg = document.getElementById("error-msg");
const okMsg = document.getElementById("ok-msg");
const mensajeCerrado = document.getElementById("mensaje-cerrado");
const tbody = document.getElementById("tbody-pasajeros");
const listaVacia = document.getElementById("lista-vacia");

function mostrarError(texto) {
  errorMsg.textContent = texto;
  errorMsg.classList.remove("oculto");
  okMsg.classList.add("oculto");
}

function mostrarOk(texto) {
  okMsg.textContent = texto;
  okMsg.classList.remove("oculto");
  errorMsg.classList.add("oculto");
}

function limpiarMensajes() {
  errorMsg.classList.add("oculto");
  okMsg.classList.add("oculto");
}

async function cargarEstado() {
  const res = await fetch("/api/estado");
  const data = await res.json();

  document.getElementById("fecha-viaje").textContent = data.fechaViaje;
  document.getElementById("cupos-disponibles").textContent = data.cuposDisponibles;
  document.getElementById("cupo-total").textContent = data.cupoTotal;
  document.getElementById("hora-cierre").textContent = data.horaCierre;

  const cerrado = data.cerrado;
  mensajeCerrado.classList.toggle("oculto", !cerrado);
  btnAnotarme.disabled = cerrado || data.cuposDisponibles <= 0;

  tbody.innerHTML = "";
  if (data.pasajeros.length === 0) {
    listaVacia.classList.remove("oculto");
  } else {
    listaVacia.classList.add("oculto");
    data.pasajeros.forEach((p, i) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${escapeHtml(p.nombre)}</td>
        <td>${escapeHtml(p.area || "")}</td>
        <td><button class="cancelar" data-id="${p.id}">Cancelar</button></td>
      `;
      tbody.appendChild(tr);
    });
  }
}

function escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  limpiarMensajes();

  const nombre = nombreInput.value.trim();
  const area = areaInput.value.trim();

  const res = await fetch("/api/inscribir", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre, area }),
  });
  const data = await res.json();

  if (!res.ok) {
    mostrarError(data.error || "No se pudo completar la inscripción");
    return;
  }

  form.reset();
  mostrarOk("¡Listo! Quedaste anotado/a para el viaje de mañana.");
  cargarEstado();
});

tbody.addEventListener("click", async (e) => {
  if (!e.target.classList.contains("cancelar")) return;
  const id = e.target.dataset.id;
  limpiarMensajes();

  const res = await fetch(`/api/inscribir/${id}`, { method: "DELETE" });
  const data = await res.json();

  if (!res.ok) {
    mostrarError(data.error || "No se pudo cancelar la inscripción");
    return;
  }
  cargarEstado();
});

cargarEstado();
setInterval(cargarEstado, 20000);
