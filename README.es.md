# repo-xray

**Documentación de arquitectura generada a partir del código.** Le indicas un proyecto a repo-xray y obtienes diagramas y páginas claros y cuidados que lo explican en tres niveles: de qué está hecho, qué hace y qué pasa cuando alguien lo usa. Todo funciona en tu ordenador, gratis, sin IA y sin cuentas.

[English](README.md) · Español

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/example-overview-dark.svg">
  <img alt="Visión general generada para Benchify, un proyecto con Spring Boot y Angular: una zona de frontend con la aplicación web, una de backend con la API, PostgreSQL con PostGIS en datos, y Firebase Auth y Firebase Storage en servicios externos" src="docs/images/example-overview-light.svg">
</picture>

<sub>Todas las imágenes de este README las ha generado repo-xray a partir del código de [Benchify](https://github.com/Maanuu77/Benchify), un proyecto full-stack con una API en Spring Boot y un frontend en Angular.</sub>

## Por qué

Un único diagrama de una aplicación real es un muro de cajas. repo-xray explica un proyecto como lo haría una persona, una pregunta cada vez, y nunca muestra más de unos nueve elementos a la vez:

| Nivel | Pregunta | Se obtiene de |
| --- | --- | --- |
| 1 · Visión general | ¿De qué está hecho? | Manifiestos de build, dependencias, imports, `compose.yaml`, `firebase.json`, archivos de nube y de CI |
| 2 · Funcionalidades | ¿Qué hace? | Carpetas de funcionalidad o cortes verticales, capas, paquetes, tags de OpenAPI, títulos de rutas |
| 3 · Flujos | ¿Qué pasa cuando…? | Llamadas seguidas desde la pantalla, pasando por la petición HTTP, hasta la base de datos |

Cada diagrama dice a cuál de las tres preguntas responde, agrupa lo que va junto en una zona (un nivel, una aplicación, un carril) y pone sus etiquetas en los huecos entre zonas, nunca encima de una tarjeta.

### ¿Qué hace?

Cada aplicación es una zona y cada funcionalidad una tarjeta con las capas que toca. Las del frontend muestran, con los colores de las del backend, a cuáles llaman, y un conector entre las zonas dice cuántas peticiones cruzan de las pantallas a la API.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/example-features-dark.svg">
  <img alt="Mapa de funcionalidades de Benchify: una zona de frontend con seis funcionalidades y una de backend con nueve, con sus descripciones, las capas que tocan y las funcionalidades a las que llaman" src="docs/images/example-features-light.svg">
</picture>

### ¿Qué pasa cuando…?

Una petición seguida desde el botón que pulsa el usuario hasta la tabla donde termina. La petición HTTP se dibuja donde cruza de una aplicación a la siguiente, con su método y su ruta, y la última tarjeta dice si la petición lee, guarda o borra.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/example-flow-dark.svg">
  <img alt="Flujo para reseñar un banco: ResenasSection.enviar, ResenasApi.publicar, POST /api/v1/bancos/{bancoId}/resenas, ResenaController.publicar, ResenaService.publicar, ResenaPersistenceAdapter.save, PostgreSQL" src="docs/images/example-flow-light.svg">
</picture>

## Cómo empezar

### La aplicación (Windows)

1. Descarga `repo-xray.exe` desde la página de Releases de este repositorio. No hace falta instalar nada más.
2. Ábrelo con doble clic. Windows puede avisar de que la aplicación no está firmada: pulsa **Más información** y después **Ejecutar de todas formas**.
3. Arrastra la carpeta de tu proyecto a cualquier parte de la ventana o pulsa **Choose folder…**.
4. Explora los diagramas y las páginas y pulsa **Export**.

<p align="center">
  <img src="docs/images/app-results.png" alt="repo-xray mostrando la visión general de Benchify: una barra lateral con todos los documentos agrupados en Overview, Features y Flows, y el diagrama con sus controles de zoom" width="860">
</p>

El zip contiene una carpeta `architecture` para el `docs/` de tu repositorio, un `README-snippet.md` para pegar en tu README y una guía `HOW-TO-USE.md`. Los diagramas van en SVG, en versión clara y oscura (GitHub elige la que corresponde al tema de cada lector), y además en PNG para presentaciones y publicaciones. El menú **Export** también guarda el diagrama que estás viendo como SVG o PNG, o lo copia al portapapeles.

### Cómo moverse

- **Tres niveles a un clic.** La barra lateral lista todos los documentos en Overview, Features y Flows; las pestañas de arriba (o `Ctrl+1`, `Ctrl+2`, `Ctrl+3`) saltan a cada nivel, y un filtro acota una lista larga por nombre, descripción o ruta.
- **Diagramas por los que moverse.** Arrastra para desplazarte, `Ctrl` + rueda para hacer zoom, doble clic para acercar, `0` para ajustar. `Ctrl+F` busca texto dentro del diagrama.
- **Tarjetas que llevan a algún sitio.** Pulsa la tarjeta de una funcionalidad para abrir su página, una aplicación para ver sus funcionalidades, un paso de un flujo para llegar a la funcionalidad a la que pertenece. Las páginas dibujan sus diagramas en su sitio y sus enlaces navegan.
- **Claro, oscuro o el del sistema.** Un solo interruptor cambia toda la ventana y el diagrama que se está viendo.
- **Un análisis honesto.** Mientras se ejecuta ves la etapa real y cuántos archivos se han leído, y puedes cancelarlo. El **Analysis report** dice qué se ha leído, las pruebas que hay detrás de cada servicio y lo que no se pudo resolver: archivos que no se pueden parsear, peticiones sin endpoint, flujos que se quedan en el controlador.

<p align="center">
  <img src="docs/images/app-flow-dark.png" alt="repo-xray con el tema oscuro mostrando un flujo, con la barra de búsqueda abierta y las coincidencias resaltadas en el diagrama" width="860">
</p>

| Teclas | Qué hacen |
| --- | --- |
| `Ctrl+O` · `F5` | Abrir otra carpeta · analizar de nuevo |
| `Ctrl+1` `Ctrl+2` `Ctrl+3` | Visión general · Funcionalidades · Flujos |
| `Ctrl+AvPág` · `Ctrl+RePág` | Documento siguiente · anterior |
| `Ctrl+K` · `Ctrl+F` | Filtrar la barra lateral · buscar en el diagrama |
| `+` `-` `0` `1` · flechas | Acercar, alejar, ajustar, 100 % · desplazarse |
| `Ctrl+T` · `Ctrl+E` · `Ctrl+Mayús+C` | Editar textos · exportar el zip · copiar el diagrama |
| `Ctrl+B` · `Ctrl+D` · `F11` | Barra lateral · claro u oscuro · pantalla completa |

### Desde el código

Necesita Python 3.11 o superior.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # en macOS o Linux: .venv/bin/python
.venv/Scripts/python -m repo_xray                           # abre la aplicación
.venv/Scripts/python -m repo_xray ruta/al/proyecto --export docs.zip
```

## Tus palabras, en tu idioma

Los nombres y las descripciones salen del propio código: `@Tag` de OpenAPI, Javadoc y JSDoc, docstrings, títulos de rutas y el primer párrafo del README del proyecto. Donde el código no dice nada, repo-xray escribe una frase construida solo con lo que ha encontrado, por ejemplo *"Pantallas: Iniciar sesión y Crear cuenta. Usa Firebase Auth."*

Los documentos siguen el idioma de los comentarios del código, inglés o español, así nunca se mezclan. En la aplicación, **Edit texts** permite renombrar funcionalidades y reescribir descripciones, con una tarjeta por funcionalidad que muestra como pista lo que se encontró, y el menú de idioma cambia entre automático, inglés y español. Lo que elijas se guarda en `xray.toml` dentro del proyecto analizado, así el siguiente análisis lo mantiene:

```toml
language = "es"
description = "Mapa colaborativo de bancos públicos."

[features."frontend/auth"]
name = "Acceso"
description = "Iniciar sesión o crear una cuenta con Firebase."
```

<p align="center">
  <img src="docs/images/app-edit-texts.png" alt="La ventana Edit texts: la descripción del proyecto y una tarjeta por funcionalidad, cada una con el nombre y la descripción encontrados como pistas" width="760">
</p>

## Qué entiende

| | |
| --- | --- |
| Lenguajes | Python (`ast`), Java y TypeScript/JavaScript (tree-sitter) |
| Backends | Endpoints de Spring Boot (`@GetMapping`, `@PostMapping`… con prefijos de clase), FastAPI y Flask (decoradores de ruta, prefijos de router y de blueprint) y NestJS (`@Controller`, `@Get`…). Django y Express se detectan por sus dependencias |
| Frontends | Angular (componentes, `inject()`, inyección por constructor, rutas), React (componentes, hooks, rutas), llamadas HTTP con `HttpClient`, `fetch` y `axios` |
| Servicios | PostgreSQL y PostGIS, MySQL, MongoDB, Redis, Kafka, RabbitMQ, Firebase Auth, Storage y Firestore, Supabase, Amazon S3, Stripe… |
| Despliegue y CI | Docker, Cloud Run, Firebase Hosting, Vercel, Netlify, Fly.io, Render, Heroku, App Engine, GitHub Actions, GitLab CI |

Añadir una tecnología es una línea en [`catalog.py`](repo_xray/analysis/catalog.py).

## Cómo funciona

```
escaneo → parseo → stack · grafo de llamadas · enlaces HTTP → funcionalidades · flujos → textos · diagnósticos → SVG, Markdown, PNG → zip
```

- **El parseo** nunca ejecuta el código analizado: Python se lee con `ast` y Java y TypeScript con tree-sitter, hacia un modelo común a todos los lenguajes. Los archivos se leen por adelantado en hilos y se recuerdan, así que refrescar tras editar un texto solo lee lo que ha cambiado.
- **Las llamadas se resuelven** a través de los tipos de los campos, los imports, las interfaces y sus implementaciones, así `resenas.publicar(...)` en un controlador llega a `ResenaService.publicar` y de ahí al adaptador de persistencia.
- **Las llamadas del frontend se enlazan con los endpoints** comparando las rutas desde el final, porque la URL base del frontend no suele conocerse: `{this.url}/bancos/{id}/resenas` encaja con `/api/v1/bancos/{bancoId}/resenas`.
- **Los diagramas** son SVG maquetados a mano con solo funciones de SVG Tiny, así los navegadores, GitHub y Qt los dibujan igual. El texto se mide para que nunca se salga de su caja, y cada diagrama se dibuja cuando se abre o se exporta por primera vez, no antes.
- **El progreso se cuenta con hechos**, la etapa que se está ejecutando y los archivos leídos hasta el momento, nunca con un porcentaje inventado.

El porqué de cada decisión está recogido en [Architecture Decision Records](docs/adr/) (en inglés): análisis estático con `ast` y tree-sitter, tres niveles exportados en un zip, una aplicación de escritorio para principiantes, un ejecutable de un solo archivo, [por qué no hay IA](docs/adr/0011-no-ai.md) y el diseño de la aplicación y de sus diagramas.

## Limitaciones

- Lee el código, no lo ejecuta. No sigue llamadas sobre variables locales ni sobre valores devueltos por otras llamadas, así que un flujo muestra el camino principal, no todas las ramas. El informe del análisis lista los flujos que se quedan cortos.
- Los flujos empiezan en endpoints HTTP de Spring, FastAPI, Flask y NestJS. Los proyectos sin ellos tienen solo los niveles 1 y 2.
- Los nombres se quedan en el idioma del código salvo que los edites; no se traduce nada automáticamente.
- La interfaz de la aplicación está en inglés; los documentos que escribe, en inglés o en español.
- El ejecutable es para Windows. En macOS y Linux se usa desde el código.

## Desarrollo

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest                         # unas 450 pruebas, incluida la aplicación
.venv/Scripts/python -m pip install -r requirements-build.txt
.venv/Scripts/python packaging/build.py                # dist/repo-xray.exe
```

El código está en el paquete `repo_xray`: `parsers/` (un módulo por lenguaje), `analysis/` (stack, capas, funcionalidades, llamadas, enlaces, flujos, textos, diagnósticos), `render/` (los tres diagramas y los componentes que comparten), `export/` (Markdown, PNG y zip) y `app/` (la aplicación de escritorio: `theme.py` e `icons.py` para su aspecto, `pages/` para sus tres pantallas, `widgets/` para la barra lateral, el lienzo de diagramas y la vista de páginas). El plan y su historia están en [docs/ROADMAP.md](docs/ROADMAP.md) y los cambios de cada versión en [CHANGELOG.md](CHANGELOG.md).

## Licencia

[MIT](LICENSE) © 2026 Manuel Martínez
