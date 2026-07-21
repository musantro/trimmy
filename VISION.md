# Visión de Trimmy

Trimmy es un editor de vídeo de escritorio centrado en transformar un vídeo
horizontal en una composición vertical de dos zonas, preparada para publicar
en redes sociales. Debe ofrecer un flujo local, rápido y comprensible: abrir
un vídeo, definir los recortes y el tramo temporal, elegir un destino y dejar
que FFmpeg produzca el archivo final.

La aplicación no es un cliente web disfrazado ni un conjunto de servicios
remotos. Es un producto desktop: PySide6 ofrece la experiencia interactiva y
FFmpeg/FFprobe realizan el trabajo multimedia local. Esa elección no reduce
la necesidad de límites arquitectónicos; hace todavía más importante separar
la interfaz de usuario, los casos de uso y las integraciones con el sistema.

## Objetivos de producto

- Hacer fácil crear clips verticales de calidad a partir de una fuente de
  vídeo local.
- Mantener el control del usuario sobre recortes, proporción de la
  composición, tramo temporal, plataforma, formato y calidad.
- Exportar resultados predecibles mediante presets explícitos y un backend de
  render sustituible.
- Ser utilizable como aplicación gráfica y automatizable desde sus puntos de
  entrada de control, sin duplicar reglas de negocio.
- Funcionar de forma local y portable en las plataformas de escritorio
  soportadas por Python y PySide6.

## Modelo arquitectónico

Trimmy adopta arquitectura hexagonal y modular. La unidad que protege la
arquitectura es el **módulo vertical**, no una capa técnica global. Cada módulo
de negocio tiene exactamente estas capas:

```text
<área>/<módulo>/
  domain/
  application/
  infrastructure/
```

Los módulos se agrupan directamente bajo áreas de negocio, sin un paquete
intermedio `contexts/`. Por ejemplo, `editing/crop` y `editing/trim` son
módulos distintos dentro del área de edición. Un módulo que no necesita un
segundo nivel, como `rendering` o `preferences`, usa las mismas tres capas en
su propia raíz.

Esta disposición conserva la lectura vertical inspirada en CodelyTV —primero
la capacidad de negocio y después sus capas— y evita una carpeta genérica que
oculte el lenguaje del producto.

### Domain

`domain` contiene el lenguaje ubicuo y las reglas que deben seguir siendo
válidas con independencia de PySide6, FFmpeg, JSON, CLI o filesystem:

- entidades, agregados, value objects y especificaciones;
- servicios puros de dominio;
- eventos de dominio;
- puertos para repositorios, gateways y buses de eventos cuando el dominio
  necesita colaborar con el exterior.

El dominio no conoce frameworks, la interfaz gráfica ni implementaciones de
adaptadores. Los valores con reglas o significado propio deben representarse
con tipos explícitos, en lugar de propagar primitivos ambiguos.

### Application

`application` expresa las intenciones del usuario y coordina el dominio.
Sus casos de uso reciben puertos por inyección de dependencias, aplican el
flujo necesario y devuelven resultados adecuados para adaptadores. No crean
backends concretos, repositorios, clientes de sistema ni widgets.

### Infrastructure

`infrastructure` implementa los puertos y aísla las dependencias externas:
FFmpeg, FFprobe, archivos JSON, almacenamiento en memoria, buses adaptados al
event loop y otras integraciones técnicas. Las implementaciones pueden
cambiar sin que el dominio ni los casos de uso cambien por ello.

## Aplicaciones de entrada

La UI desktop no es un bounded context de negocio. Es una aplicación que
compone y consume los módulos:

```text
apps/desktop/
  bootstrap.py
  main_window.py
  views/
  widgets/
  controllers/
  presenters/
```

La aplicación desktop puede llamar casos de uso en el mismo proceso; no es
necesario introducir HTTP ni un backend artificial para conservar los límites
hexagonales. La CLI y el control local son otros adaptadores de entrada y
deben invocar la misma frontera de aplicación, no manipular widgets ni estado
privado de la ventana.

`bootstrap.py` es el composition root. Es el único lugar de una aplicación
donde se decide qué adaptador concreto satisface cada puerto y donde se crean
repositorios, gateways, buses y casos de uso. Widgets, vistas, workers y
controladores reciben sus dependencias; no las construyen.

## Reglas de dependencia

- `domain` no depende de `application`, `infrastructure` ni `apps`.
- `application` depende de `domain` y de sus puertos, nunca de
  implementaciones de infraestructura.
- `infrastructure` puede depender de `domain` y `application` para adaptar
  puertos, pero no de `apps`.
- Las aplicaciones pueden depender de los módulos de negocio; los módulos de
  negocio nunca dependen de las aplicaciones.
- Los módulos hermanos no importan detalles internos entre sí. La colaboración
  se realiza por contratos publicados, eventos o una frontera de aplicación
  explícita.
- `shared` sólo contiene conceptos realmente transversales y no puede
  depender de los módulos de producto.

## Fuente de verdad y consistencia

El estado de negocio no debe residir en widgets. La interfaz mantiene sólo
estado de presentación efímero —foco, selección visual, geometría de la
ventana o animaciones—. El estado que define una edición, un recorte, un tramo
temporal, una preferencia o un render pertenece al dominio o a una frontera de
aplicación explícita y se modifica mediante casos de uso.

Las preferencias globales de usuario se distinguen del estado de una edición.
Los repositorios persisten agregados o configuraciones con identidad clara; no
se usan para esconder estado mutable de un widget.

## Criterios de diseño

Al tomar decisiones de diseño, Trimmy prioriza:

1. **Claridad del lenguaje de negocio.** Los nombres representan conceptos de
   edición y render, no detalles accidentales de la UI o de FFmpeg.
2. **Dependencias hacia dentro.** La lógica central debe poder probarse sin
   arrancar Qt, FFmpeg ni el sistema de archivos.
3. **Módulos pequeños y explícitos.** Se crea un módulo cuando tiene lenguaje,
   reglas o ciclo de cambio propios; no se crean paquetes genéricos como
   `utils`, `common` o `helpers`.
4. **Adaptadores sustituibles.** FFmpeg, FFprobe, persistencia y mensajería se
   expresan mediante puertos y se conectan en el composition root.
5. **DI explícita.** Se prefiere inyección manual por constructor a estado
   global, service locators o wiring repartido por la UI.
6. **Pragmatismo desktop.** No se fuerza una separación de procesos cuando una
   frontera de paquetes, contratos y dependencias en proceso es suficiente.
7. **Evolución segura.** Las decisiones arquitectónicas importantes se
   codifican como standards ejecutables, no sólo como documentación.

## Verificación continua

Los tests de standards son parte del producto arquitectónico. Deben comprobar
la estructura de módulos y capas, las direcciones de importación, el
aislamiento de frameworks del dominio, la independencia entre módulos
hermanos, la dependencia unidireccional entre `apps` y el core, y la
centralización de la composición en los bootstraps.

La calidad se completa con formato, lint, chequeo estático de tipos, pruebas
unitarias con cobertura estricta del core y una comprobación de que el paquete
redistribuible se construye e instala correctamente. El objetivo no es sumar
ceremonia: es impedir que una futura mejora funcional erosione los límites que
permiten mantener Trimmy.
