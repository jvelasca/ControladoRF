# Manual de usuario — CONTROLADORF

Guía para operadores de RF y personal de producción.

---

## 1. Para qué sirve

CONTROLADORF le ayuda a **organizar el inventario inalámbrico** del espectáculo y a **vigilar las frecuencias en directo**:

- Guardar micrófonos, IEM, intercoms y sus frecuencias en un **proyecto**.
- Importar listados desde **Shure Wireless Workbench**.
- Ver el **espectro en tiempo real** y recibir **avisos** si una portadora pierde calidad.

---

## 2. Primeros pasos

1. **Archivo → Nuevo** o **Abrir** — elija o cree un proyecto (`.crf`).
2. En **Inventario RF**, revise o añada canales (nombre, frecuencia, modelo, zona…).
3. **Archivo → Guardar** — guarde con frecuencia durante el montaje.
4. Cambie de módulo con las pestañas superiores: **Inventario**, **Monitor**, etc.

**Workspace:** en **Herramientas → Workspaces** puede guardar disposiciones de paneles (tamaños y visibilidad) para distintos puestos de trabajo.

---

## 3. Inventario RF

| Tarea | Cómo hacerlo |
|-------|----------------|
| Nuevo canal | Botón nuevo o **Ctrl+N** |
| Editar | Seleccionar fila y **F2**, o panel Propiedades |
| Duplicar | **Ctrl+D** |
| Eliminar | **Supr** |
| Aplicar cambios | **Ctrl+S** en propiedades |
| Deshacer edición | **Esc** |

Puede mostrar u ocultar columnas y exportar el inventario desde el panel de acciones.

---

## 4. Monitor — visión general

En el módulo **Monitor**:

1. Configure la **fuente** (radio SDR) en el panel lateral.
2. Pulse **Play** en la barra superior para iniciar la captura.
3. Ajuste **frecuencia central**, **span** y ganancias según necesite.
4. Use **Analizador** para espectro/waterfall o **SDR** para escuchar demodulación.

Los **marcadores** del inventario pueden mostrarse sobre el espectro cuando la supervisión está activa.

---

## 5. Supervisión y alarmas (resumen)

La **supervisión** comprueba que cada canal del inventario mantiene una señal aceptable respecto al ruido ambiente.

**Requisitos:** proyecto abierto, inventario cargado y **Play** activo.

| Acción | Dónde |
|--------|--------|
| Ver estado de canales | Panel **Alarmas** → **Ver eventos** (o **F3**) |
| Umbrales (cuándo avisar) | **Umbrales…** o **F5** |
| Atender una alarma | Clic derecho en el canal → **Atender**, o **F9** |
| Atender todas | Botón en barra de supervisión o **F4** |
| Histórico | **F6** |
| Informe para archivo | **F7** (texto con fechas y duración) |
| Localizar en espectro | Seleccionar canal y **F8** |

Guía detallada: menú **Ayuda → Supervisión Monitor**.

---

## 6. Atajos útiles (Monitor activo)

| Tecla | Función |
|-------|---------|
| **F1** | Ayuda de supervisión |
| **F2** | Iniciar / detener captura |
| **F3** | Ventana de supervisión |
| **F4** | Atender todas las alarmas |
| **F5** | Umbrales |
| **F6** | Histórico |
| **F7** | Exportar informe |
| **F8** | Localizar canal |
| **F9** | Atender canal seleccionado |
| **F10** | Disparo manual de barrido |

---

## 7. Consejos habituales

- **Guarde el proyecto** antes de ensayos y antes de cerrar la aplicación.
- Si no ve alarmas, compruebe que **Play** está en marcha y que el canal no está marcado como «no supervisado» (texto tachado en el árbol).
- Los **umbrales** más específicos (un solo canal) prevalecen sobre los generales del proyecto.
- Para cambiar idioma: **Herramientas → Configuración → Idioma**.

---

## 8. Más ayuda

- **Ayuda → Manual de usuario** — este documento.
- **Ayuda → Supervisión Monitor** — alarmas, umbrales e informes.
- **Ayuda → Acerca de…** — versión de la aplicación.

*© CONTROLADORF — J. Alberto Velasco*
