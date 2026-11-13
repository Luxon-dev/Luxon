LUXON 2.0 - INSTALACION Y PUESTA EN MARCHA
==========================================

ARCHIVOS PRINCIPALES
- index.html: tienda online para GitHub Pages.
- app.py: administrador de Windows. Sigue editando el catálogo dentro de index.html y conserva la publicación Git.
- worker.js + wrangler.toml: intermediario seguro para el chatbot IA con Gemini.

1) ACTUALIZAR LA TIENDA
- Hacé una copia de seguridad de tu carpeta/repositorio actual.
- Reemplazá index.html y app.py por los nuevos archivos.
- No cambies el nombre index.html.
- Ejecutá app.py desde la misma carpeta del repositorio.
- La clave de administrador sigue siendo luxon2026 (se puede cambiar con LUXON_DEV_PASSWORD).
- El resto de funciones del catálogo, carrito y pedido por WhatsApp se conserva.

2) CONFIGURAR EL CHATBOT IA (UNA SOLA VEZ)
El HTML no contiene ni debe contener la clave de Gemini. El chatbot queda visualmente integrado, pero no responde con IA hasta que se despliegue el Worker y se configure su URL.

A. Crear una clave de Gemini
- Entrá a Google AI Studio: https://aistudio.google.com/app/apikey
- Creá una API key para Gemini y guardala en un lugar seguro.
- No la pegues en index.html, app.py, GitHub ni en el panel de configuración del sitio.

B. Crear el Worker
- Creá una cuenta en Cloudflare: https://dash.cloudflare.com/
- Instalá Node.js si todavía no está instalado.
- Abrí CMD dentro de esta carpeta (donde está worker.js).
- Ejecutá: npx wrangler login
- Abrí wrangler.toml y reemplazá https://TU-USUARIO.github.io por el origen exacto de tu tienda.
  Ejemplo: si tu web es https://elian.github.io/luXon/, el origen es https://elian.github.io (sin la ruta /luXon/).
  Si usás un dominio propio, colocá https://tudominio.com.
- Ejecutá: npx wrangler secret put GEMINI_API_KEY
- Pegá la clave de Gemini cuando la terminal la solicite.
- Ejecutá: npx wrangler deploy
- Cloudflare mostrará una URL similar a https://luxon-assistant.<tu-cuenta>.workers.dev

C. Conectar el Worker a la tienda
- Abrí la aplicación app.py.
- Entrá en Asistente IA.
- Pegá la URL del Worker terminada en /chat.
  Ejemplo: https://luxon-assistant.<tu-cuenta>.workers.dev/chat
- Presioná Guardar configuración y publicar.
- Esperá que GitHub Pages actualice el sitio.
- Probá el endpoint de salud abriendo la URL del Worker terminada en /health. Debe devolver ok:true.
- Abrí la tienda y probá el asesor virtual.

3) SEGURIDAD Y COSTOS
- La clave Gemini permanece como Secret en Cloudflare; nunca se publica en GitHub.
- El Worker solo acepta el origen configurado y limita el tamaño de las consultas.
- El límite simple por IP dentro del Worker es una protección adicional, no un sistema global persistente. Para producción, configurá una regla de Rate Limiting en Cloudflare (por ejemplo, 10-20 solicitudes por minuto por IP en /chat) y revisá el consumo de Gemini.
- Revisá los precios y límites actuales de Gemini antes de habilitar tráfico público. La API puede generar costos según el uso y el modelo.
- La IA recomienda según el catálogo recibido, pero no conoce el stock real ni confirma envíos, descuentos o disponibilidad. El cierre de compra continúa por WhatsApp.

4) ADMINISTRACION Y PUBLICACION
- Seguí ejecutando app.py dentro de tu repositorio Git.
- Los cambios de productos, portada y configuración del chat se guardan en index.html.
- La publicación automática prepara index.html, app.py, worker.js, wrangler.toml, README_LUXON_2.txt y .gitignore cuando esos archivos existen en la carpeta.
- Con Publicar automáticamente activo, la app hace commit y push a la rama actual.
- El código del Worker es independiente del repositorio de GitHub Pages. Si modificás worker.js, volvé a ejecutar npx wrangler deploy.

5) NOTAS
- El número de WhatsApp que ya tenía el catálogo se conserva en esta versión.
- Los favoritos se guardan localmente en el navegador del visitante.
- No se añadió pasarela de pagos: el proceso de compra sigue siendo consulta/pedido por WhatsApp, como solicitaste.

6) NOVEDADES VISUALES E INTERACTIVAS - LUxon 2.1
- LuXon Discovery Studio: selector guiado por intención de compra y presupuesto. Filtra y prioriza productos existentes del catálogo; no inventa artículos.
- Comparador de hasta 3 productos: compara precio, categoría, variantes y descripción. Permite consultar cada opción por WhatsApp.
- Vistos recientemente: guarda hasta 8 productos en el almacenamiento local del navegador del visitante.
- Las nuevas funciones están integradas en index.html y no requieren cambiar worker.js ni volver a desplegar el Worker.
- Para actualizar la web, reemplazá index.html en tu repositorio y publicá desde app.py como siempre.

7) NOVEDADES - LUXON 2.2: EXPERIENCIA PARA VOLVER
- Favoritos accesibles desde el encabezado, con contador, panel propio, opción de quitar productos y compartir la selección por WhatsApp.
- Descubrimiento LuXon del día: rota diariamente entre productos activos del catálogo. No inventa descuentos ni disponibilidad.
- Compartir producto: cada tarjeta permite enviar el producto y el enlace actual de la tienda por WhatsApp.
- Inspiración LuXon: sección editorial con guías breves para orientar la elección.
- Preguntas frecuentes desplegables: explica compra, confirmación de precios, envíos, favoritos y asesoramiento.
- Mensaje de bienvenida en la segunda visita: se activa localmente en ese navegador; no recopila datos personales.
- Mejoras de metadatos para título, descripción y vista previa al compartir el sitio.
- Estas funciones nuevas viven en index.html. No requieren cambios en app.py ni redeploy del Worker.
- Los favoritos y el contador de visitas se guardan localmente en el dispositivo del visitante. Si borra los datos del navegador o cambia de dispositivo, no se sincronizan.
