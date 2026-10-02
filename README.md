# DE4DC0DEX

Bot moderador para grupos de Telegram: protege un grupo del spam.

Tiene **el cerebro** (las reglas), **un simulador** para verlo trabajar sin
Telegram y **el adaptador** que lo pone en un grupo de verdad.

**Supuesto de base: un grupo de compra-venta y servicios.** Nadie charla,
cada mensaje es un aviso. Las reglas y sus números están pensados para eso,
así que son más duras que las de un grupo de amigos.

## Probarlo

Hace falta Python 3.10 o más nuevo. El simulador no necesita instalar nada.

```
cd S:\tools\DE4DC0DEX
python -m de4dc0dex.sim
```

Abrí <http://127.0.0.1:4390>. Para usar otro puerto: `python -m de4dc0dex.sim 4391`.
Los tests se corren así:

```
python -m unittest -v
```

## Cómo está armado

```
de4dc0dex/
  core/                el cerebro: no sabe nada de Telegram
    events.py          lo que pasa en el grupo (entró alguien, un mensaje...)
    actions.py         lo que el bot decide hacer (borrar, silenciar...)
    decision.py        la respuesta: acciones + el porqué, paso a paso
    moderator.py       la puerta de entrada: evento -> reglas -> decisión
    state.py           lo que el bot recuerda de cada miembro
    store.py           esa memoria guardada en SQLite, para los reinicios
    config.py          las perillas (tiempos, límites)
    rules/
      verification.py  botón "Verificar" para los que entran
      flood.py         muchos mensajes seguidos
      links.py         links (prohibidos) y reenvíos de los que recién entraron
      repeat.py        el mismo mensaje dos veces seguidas
      warns.py         advertencias (3 = silencio)
      names.py         avisa cuando alguien se cambia el nombre
      commands.py      /warn /mute /ban y compañía
  tg/                  el bot de verdad: python -m de4dc0dex.tg
    bot.py             updates de Telegram -> eventos, acciones -> API
    translate.py       las traducciones que no tocan la red (con tests)
  sim/                 el grupo de mentira
    session.py         arma eventos, llama al cerebro, aplica las acciones
    __main__.py        el servidor web del simulador
    static/            la página
tests/                 un archivo de tests por regla
```

La idea central es una sola: **el cerebro recibe eventos y devuelve
decisiones, sin ejecutar nada.** Eso tiene tres ventajas:

1. **Se puede simular.** El simulador y el bot real llaman a
   `Moderator.handle(evento, hora)` exactamente igual. Lo que funciona en uno
   funciona en el otro.
2. **Se puede testear.** Un test arma un evento, se lo pasa al cerebro y
   mira qué acciones volvieron. No hace falta internet, ni Telegram, ni
   esperar dos minutos a que venza una verificación: la hora la pone el test.
3. **Se lee.** Cada regla es un archivo corto que se entiende solo.

### El recorrido de un mensaje

`Moderator._on_message` lo pasa por estas etapas, en orden:

1. **Permisos.** Si la persona está sin verificar o silenciada, Telegram ni
   siquiera deja que el mensaje exista. El simulador lo muestra con la
   etiqueta «Telegram lo frena».
2. **Nombres.** Si quien escribe (o a quien le responden) aparece con otro
   nombre que el que el bot tenía anotado, avisa en el grupo.
3. **Comandos.** Si empieza con `/`, va a `commands.py` y no pasa por los
   filtros.
4. **Admins.** A los admins no se les aplican los filtros.
5. **Filtros**: anti-flood, anti-links y anti-repetición. El primero que
   salta corta la cadena, porque si el mensaje ya se borró no tiene sentido
   seguir. El anti-repetición va último porque anota los mensajes que pasan:
   uno que otra regla borró no cuenta como "ya lo mandaste".

## Qué hace

| Regla | Qué mira | Qué hace |
|---|---|---|
| Verificación | Alguien entra | Le saca el permiso de escribir y le pone un botón. Si no lo toca en 2 min, lo saca (puede volver a intentar). |
| Anti-flood | Más de 5 mensajes en 8 s | Borra el que se pasó y 10 min de silencio. |
| Anti-links | Cualquier link, de cualquier cuenta que no sea admin. Y los reenvíos de canal durante las primeras 24 h en el grupo | Borra el mensaje y suma una advertencia. |
| Anti-repetición | El mismo mensaje dos veces en menos de 15 min, sin importar mayúsculas ni espacios. Cuentan todos, hasta los cortos | Borra la repetición y avisa cuánto falta. |
| Advertencias | Llegar a 3 | 24 h de silencio y el contador vuelve a 0. |
| Cambios de nombre | El nombre con que aparece alguien, contra el que el bot tenía anotado | Avisa en el grupo el nombre viejo y el nuevo. Si es admin, solo lo anota en el registro. |

Telegram no le avisa al bot cuando alguien se cambia el nombre. El bot lo nota
recién cuando esa persona escribe, toca un botón o alguien le responde un
mensaje.

**Las ediciones también se miran.** El truco es publicar algo limpio y
después meterle un link editando. Una edición pasa solo por el anti-links:
si agrega un link, se borra y suma una advertencia («link agregado al editar
un mensaje»); si es el texto de un álbum, se borra el álbum entero. El
anti-flood y el anti-repetición no aplican (editar no manda nada nuevo ni
sube el aviso en el chat) y una edición tampoco ejecuta comandos.

**Un álbum de fotos es un solo aviso.** Telegram lo manda como un mensaje
por foto; el adaptador espera a que lleguen todas (un segundo y medio desde
la última) y se lo pasa al cerebro como uno. Así un álbum de 10 fotos cuenta
como 1 mensaje para el anti-flood, y si hay que borrarlo (un link, una
repetición) se borra entero con un solo aviso. Un álbum sin texto se compara
por sus fotos: el mismo álbum reenviado es una repetición; las mismas fotos
subidas de nuevo desde la galería son fotos nuevas para Telegram.

Comandos: `/reglas` y `/warns` son para todos. `/warn [motivo]`, `/unwarn`,
`/mute [minutos]`, `/unmute`, `/ban [motivo]` y `/unban` son solo para admins.
Apuntan a alguien de dos formas: **respondiendo** a un mensaje suyo, o
poniendo su **@usuario** primero (`/ban @Laura ofrecer servicios sexuales`).
El @ solo anda con cuentas que el bot ya vio escribir o entrar: Telegram no le
deja a un bot buscar a alguien por su @usuario. Para las demás, respondiendo.

El aviso del ban lleva el motivo si lo hay («Laura [5] recibió un ban
permanente por ofrecer servicios sexuales.») y, si no, solo avisa el ban.

Todo mensaje del bot que nombra a alguien pone su id entre corchetes al lado
del nombre. El nombre se cambia cuando uno quiere; el id no, así que con él
se sigue a una cuenta aunque aparezca con otro nombre.
Además, el ban borra todos los mensajes que esa cuenta mandó al grupo
(`revoke_messages` de Telegram). No se puede deshacer: un `/unban` no los
devuelve.

`/reglas` contesta una vez cada 15 minutos por persona. Pedirlas de nuevo
antes se borra sin respuesta y suma una advertencia. Los admins no tienen
límite.

Las reglas de `/reglas` son generales, para cualquier tipo de grupo. La 6
(contenido prohibido: ban directo) no la aplica ninguna regla automática: es el
`/ban` de un admin.

Los números se cambian en `de4dc0dex/core/config.py`.

## La memoria en disco

`Moderator(store=Store("de4dc0dex.db"))` arranca desde lo que quedó guardado en ese
archivo y guarda después de cada evento, solo lo que cambió. Sin `store`
(el simulador, los tests) todo vive en memoria como antes. Las reglas no
saben la diferencia.

Se guardan los miembros (nombre, @usuario, advertencias, silencio,
verificación pendiente, cuándo entró) y los baneados. Los tiempos del
anti-flood y los textos del anti-repetición no se guardan: duran minutos.

El bot de verdad tiene que pasarle `time.time()` como hora. Así un silencio o
una verificación vencen a su hora aunque el bot haya estado apagado.

## Ponerlo en un grupo de Telegram

1. **Crear el bot.** En Telegram, hablale a @BotFather: `/newbot`, un nombre
   y un @usuario que termine en `bot`. Te da un token.
2. **Configurar.** Copiá `.env.example` como `.env` y poné el token en
   `DE4DC0DEX_TOKEN`. El `.env` no se sube al repo.
3. **Instalar** (una sola vez): `pip install -r requirements.txt`.
4. **Arrancar:** `python -m de4dc0dex.tg`. Queda escuchando hasta que lo cortes con
   Ctrl+C. Lo que hace sale en la consola.
5. **Sumarlo al grupo y hacerlo admin**, con permiso para borrar mensajes y
   para banear. Sin eso no ve los mensajes ni puede sancionar.

### Que arranque solo con Windows

```
.\autoarranque.ps1
```

Pone un acceso directo en la carpeta de Inicio: desde el próximo inicio de
sesión, DE4DC0DEX arranca solo y sin ventana (`pythonw`). Lo que normalmente sale en
la consola va a `data\de4dc0dex.log`. Si se cae (por ejemplo, porque todavía no hay
internet), vuelve a intentar a los 30 s. El mismo script lo maneja:
`-Iniciar` lo prende ya, `-Detener` lo apaga, `-Estado` dice si arranca solo,
si está corriendo y muestra lo último del registro, y `-Quitar` saca el
arranque automático.

Corre una sola copia por vez: si ya hay un DE4DC0DEX andando, `python -m de4dc0dex.tg`
avisa y no arranca. Dos a la vez se pelearían por los mensajes.

Restringir solo anda en **supergrupos**. Si la consola avisa que es un grupo
básico: Editar grupo > Historial del chat para nuevos miembros > Visible, y
Telegram lo convierte.

Para probarlo hace falta una segunda cuenta: el bot no modera al dueño ni a
los admins.

La memoria queda en `data/<id del grupo>.db`, una por grupo. Al lado,
`<id>.said.json` anota qué mensaje es cada desafío de verificación, para
poder borrarlo aunque el bot se haya reiniciado en el medio.

Con `DE4DC0DEX_NOTIFY_CHAT` el bot avisa en ese chat cada vez que se conecta. El
registro (quién entró, a quién sancionó) sale en la consola: en el grupo cada
cosa ya tiene su mensaje. Para saber el id de tu chat privado, mandale
`/start` al bot por privado: te lo contesta.

## Lo que falta

Nada anotado por ahora.
