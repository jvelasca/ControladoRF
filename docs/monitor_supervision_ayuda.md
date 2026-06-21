# Ayuda — Supervisión RF

Guía para el operador del módulo **Monitor → Supervisión**.

---

## 1. Qué hace la supervisión

Comprueba **todos los canales del inventario** mientras el espectro está en marcha:

- Mide la calidad de la señal (SNR) en la frecuencia de cada canal.
- Muestra **aviso** o **alarma crítica** si la señal cae por debajo de los umbrales.
- Permite **atender** incidencias y consultar un **histórico**.
- Genera **informes** para archivo (CSV o texto).

**Necesita:** proyecto abierto, canales en el inventario y botón **Play** activo.

---

## 2. Ventana de supervisión (F3)

Abra desde el panel **Alarmas → Ver eventos** o con **F3**.

### Barra superior

| Botón | Para qué sirve |
|-------|----------------|
| Ventana flotante | Árbol en ventana independiente |
| Umbrales | Reglas de aviso/crítica (**F5**) |
| Agrupar | Orden del árbol (zona, tipo, modelo…) |
| Localizar | Centrar espectro en el canal (**F8**) |
| REC | Iniciar/detener sesión de log |
| Reloj | Hora y duración de la sesión REC |
| Configuración | Carpetas y modos de log |
| Abrir último registro | Ver CSV y carpeta de la última sesión |
| (i) | Esta ayuda contextual |

### Árbol de canales

- **Clic** en un canal → resalta en espectro (no mueve el span).
- **Localizar (F8)** → centra el espectro en el canal o rama.
- **Clic derecho** → supervisar, atender, umbrales, exportar/ver log.
- Canales **no supervisados** aparecen atenuados.

---

## 3. Panel Alarmas (lateral)

Barra compacta: ventana flotante · umbrales · agrupar · localizar · **REC** · reloj · configuración · abrir último registro · (i) ayuda.

- **Ventana flotante (F3):** árbol de supervisión independiente del panel lateral.
- **Umbrales (F5):** reglas de aviso/crítica por proyecto, zona, tipo o canal.
- **Agrupar:** orden del árbol (zona, fabricante, modelo…).
- **Localizar (F8):** centra el espectro en el canal seleccionado (clic simple en el árbol solo resalta).
- **REC:** inicia o detiene una sesión de log (carpeta propia con CSV, TXT y metadatos).
- **Reloj:** hora de inicio y duración en curso; tras parar, resumen de la última sesión.
- **Configuración (engranaje):** carpetas de log/exportación, disparo CSV y inicio de REC (manual o al pulsar Play).
- **Abrir último registro:** visor del CSV de la última sesión y carpeta en el explorador.

Menú contextual del árbol: supervisar, atender, umbrales de ámbito, exportar/ver log filtrado.

---

## 4. Barra de estado de la aplicación

Zona permanente inferior (junto a la ruta del proyecto y el workspace):

| Elemento | Función |
|----------|---------|
| **Verde (n)** | Canales OK — clic abre alarmas |
| **Naranja (n)** | Avisos y menores — clic abre alarmas |
| **Rojo (n)** | Críticas — clic abre alarmas |
| **REC** | Mismo control que en el panel Alarmas |
| **Reloj** | Sesión REC activa o última sesión cerrada |
| **Abrir** | Último registro de supervisión |
| **Engranaje** | Configuración de logs |

Los números aparecen entre paréntesis junto a cada indicador de color.

---

## 5. Registro REC y log CSV

Cada sesión REC crea una subcarpeta con:

- `alarms.csv` — eventos en vivo (transiciones, ack…).
- `report.txt` — informe legible al cerrar la sesión.
- `session.json` — metadatos (inicio, fin, duración, recuento).

**Inicio de REC:** manual (botón REC) o automático al pulsar **Play** (configurable).

**Disparo del CSV:** solo con REC, al pulsar Play, o automático mientras el motor está activo (configurable).

Puede activar REC **sin Play**; la carpeta se crea vacía hasta que haya captura.

Rutas por defecto: carpeta personalizada → `{proyecto}/logs/supervision/` → Documents.

---

## 6. Umbrales — cuándo suena la alarma

Los umbrales miden la señal **respecto al ruido del entorno**, no en dBm absolutos.

| Nivel | Significado habitual (valores por defecto) |
|-------|---------------------------------------------|
| **Aviso** | Señal apenas por encima del ruido (≈ 6 dB) |
| **Crítico** | Señal muy débil (≈ 3 dB sobre ruido) |

Puede definir valores distintos para:

- Todo el **proyecto** (por defecto).
- Una **zona** (escenario, FOH…).
- Un **tipo** de equipo (micrófono, IEM…).
- Un **fabricante** o **modelo**.
- Un **canal** concreto.

Regla práctica: lo más específico gana (un canal concreto prevalece sobre el resto).

En el diálogo de umbrales, **Restablecer herencia** vuelve a usar los valores del nivel superior.

---

## 7. Estados de alarma

| Estado | Qué significa | Qué hacer |
|--------|---------------|-----------|
| **Aviso activo** | Señal baja ahora | Comprobar TX, antena, distancia, interferencias |
| **Crítico activo** | Señal muy baja o ausente | Acción urgente en el canal |
| **Memorizado** | La señal ya se recuperó, pero quedó registrado | **Atender** cuando haya revisado la causa |
| **Atendido** | Operador confirmó la incidencia | Ninguna acción pendiente |

**Atender** no arregla la RF por sí solo: confirma que ha visto y gestionado la incidencia.

---

## 8. Histórico y exportación (F6 / F7)

**Histórico:** filtre por severidad, fase o texto. Vea hora, canal, tipo de evento y detalle.

**Exportar:**

- **CSV** — listado detallado (una fila por evento).
- **TXT (informe)** — resumen por **incidentes** con hora de inicio, fin, duración y causa. Útil para partes o archivo del show.

---

## 9. Atajos de teclado (Monitor activo)

| Tecla | Función |
|-------|---------|
| **F1** | Esta ayuda |
| **F2** | Play / Stop |
| **F3** | Ventana supervisión |
| **F4** | Atender todas |
| **F5** | Umbrales |
| **F6** | Histórico |
| **F7** | Exportar informe TXT |
| **F8** | Localizar canal |
| **F9** | Atender canal seleccionado |
| **F10** | Disparo manual de barrido |

---

## 10. Si algo no funciona

| Problema | Revise |
|----------|--------|
| No hay alarmas | ¿Play activo? ¿Canal supervisado? ¿Frecuencia correcta en inventario? |
| Umbrales no cambian | ¿Guardó en el diálogo? ¿Editó el ámbito correcto (canal vs proyecto)? |
| Histórico vacío | ¿Ha habido incidencias? ¿Proyecto guardado? |
| F8 / F9 sin efecto | Abra la ventana (**F3**) y seleccione un canal en el árbol |
| Exportación vacía | Quite filtros en el histórico o amplíe el rango de fechas |
| REC sin eventos | ¿Play activo durante la sesión? ¿Canales supervisados con incidencias? |
| No abre último registro | Debe existir al menos una sesión REC cerrada o activa |

---

*ControladoRF — Supervisión RF*
