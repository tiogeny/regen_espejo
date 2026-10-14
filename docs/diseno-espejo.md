# Dirección visual e interacción

Referencia: `WhatsApp Image 2026-10-05 at 4.53.06 PM.jpeg`.
Skill instalada con `npx skills add anthropics/skills --skill frontend-design --agent codex --yes` desde https://skills.sh/anthropics/skills/frontend-design.

Paleta: oliva profundo #252b1b, vidrio oliva #39412b, marfil #f3e9d3, luz dorada #dfc185, salvia #a5b68b, tierra #6b5439.
Tipografía: Optima/Candara con alternativas locales Segoe UI y sans-serif; pesos ligeros en títulos, cifras claras y textos de ayuda con contraste. Sin fuentes de red.

Composición: un espejo con aro cálido es el elemento principal. La guía y la zona seleccionada viven sobre el rostro; un panel discreto muestra solo mediciones disponibles. En el celular se apilan guía, resultado localizado y cuestionario. El acceso conserva 1234.

```
       Derma                         conexión local
   ( aro cálido / guía )             zona señalada
   ( rostro + marcador )             área segmentada
   (                   )             orientación
              instrucción de captura
```

Revisión contra la referencia: conservar aro, líneas finas, vidrio y colores botánicos. No usar la foto como fondo ni copiar sus valores de pH, hidratación o fórmulas; el equipo no mide esas variables. Sin gráficas decorativas que parezcan mediciones reales.

## Espejo central con estadísticas laterales (2026-10-06)

Se aplicó `ui-ux-pro-max`: sistema de diseño para espejo dermatológico táctil,
búsquedas de accesibilidad/tamaño táctil y composición adaptable. Se conservó
la identidad botánica en lugar de adoptar la paleta azul genérica sugerida.

Tokens: fondo #171d16, superficie #252e23, texto #f3eedf, secundario #c1c9b6,
aro/acción #dfc185, mediciones #a5b68b. Optima/Candara/Segoe UI locales.

Composición: ampliación y mediciones a la izquierda; cámara circular centrada
con aro cálido; resumen y recomendaciones a la derecha. Estado e interacción
debajo del círculo. Encabezado con marca y conexión. Controles de 44–48 px,
separación de 8–10 px, barras animadas con movimiento reducido respetado.
Sin filtros de desenfoque sobre el vídeo ni fuentes o dependencias de red.

En anchuras inferiores a 1000 px, el círculo sigue centrado y los paneles pasan
debajo; en menos de 540 px se apilan con desplazamiento vertical. En pantalla
1280×720 y 1280×800, los controles caben sin desplazamiento vertical.

Verificación: 18 pruebas del servidor/cuestionario y Chromium sintético en
320×640, 390×844, 1280×720, 1280×800 y 1080×1920; centrado, ausencia de
superposición horizontal, formulario por sexo, recomendaciones, reinicio,
privacidad de presentación, desconexión y cero errores JS/CSP.
Captura sintética de revisión: /tmp/regen-centered-synthetic-1280x800.png.

Desplegado en la Raspberry 192.168.1.48. Respaldo de HTML/CSS/JS anteriores:
/opt/derma-onedge/backups/centered-20261006-01/src/mobile/.

Se intercambiaron los lados por petición del usuario: resumen/recomendaciones
ahora a la izquierda; mediciones/ampliación a la derecha. Chromium verificó los
cinco tamaños y el CSS se desplegó en la Pi con el kiosco reiniciado.
Respaldo CSS: /opt/derma-onedge/backups/swapped-20261006-01/mirror.css.
