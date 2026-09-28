# ICE

Bot moderador para grupos de Telegram. En *Neuromante*, el ICE es el hielo
que protege un sistema de los intrusos; este protege un grupo del spam.

Por ahora tiene **el cerebro** (las reglas) y **un simulador** para verlo
trabajar sin Telegram. La conexión con Telegram es el paso siguiente.

**Supuesto de base: un grupo de compra-venta y servicios.** Nadie charla,
cada mensaje es un aviso. Las reglas y sus números están pensados para eso,
así que son más duras que las de un grupo de amigos.

## Probarlo

Hace falta Python 3.10 o más nuevo. El simulador no necesita instalar nada.

```
cd S:\tools\ICE
python -m ice.sim
```

Abrí <http://127.0.0.1:4390>. Para usar otro puerto: `python -m ice.sim 4391`.
Los tests se corren así:

```
python -m unittest -v
```

## Cómo está armado

```
ice/
  core/                el cerebro: no sabe nada de Telegram
    events.py          lo que pasa en el grupo (entró alguien, un mensaje...)
    actions.py         lo que el bot decide hacer (borrar, silenciar...)
    decision.py        la respuesta: acciones + el porqué, paso a paso
    moderator.py       la puerta de entrada: evento -> reglas -> decisión
    state.py           lo que el bot recuerda de cada miembro
    config.py          las perillas (tiempos, límites)
    rules/
      verification.py  botón "Verificar" para los que entran
      flood.py         muchos mensajes seguidos
      links.py         links (prohibidos) y reenvíos de los que recién entraron
      repeat.py        el mismo mensaje dos veces seguidas
      warns.py         advertencias (3 = silencio)
      names.py         avisa cuando alguien se cambia el nombre
      commands.py      /warn /mute /ban y compañía
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

Comandos: `/reglas` y `/warns` son para todos. `/warn [motivo]`, `/unwarn`,
`/mute [minutos]`, `/unmute`, `/ban [motivo]` y `/unban` son solo para admins.
Apuntan a alguien de dos formas: **respondiendo** a un mensaje suyo, o
poniendo su **@usuario** primero (`/ban @Laura ofrecer servicios sexuales`).
El @ solo anda con cuentas que el bot ya vio escribir o entrar: Telegram no le
deja a un bot buscar a alguien por su @usuario. Para las demás, respondiendo.

El aviso del ban lleva el motivo si lo hay («Laura recibió un ban permanente
por ofrecer servicios sexuales.») y, si no, solo avisa el ban.
Además, el ban borra todos los mensajes que esa cuenta mandó al grupo
(`revoke_messages` de Telegram). No se puede deshacer: un `/unban` no los
devuelve.

Las reglas de `/reglas` son generales, para cualquier tipo de grupo. La 6
(contenido prohibido: ban directo) no la aplica ninguna regla automática: es el
`/ban` de un admin.

Los números se cambian en `ice/core/config.py`.

## Lo que falta

- **Conectarlo a Telegram**: un adaptador con [aiogram](https://aiogram.dev)
  que traduzca los updates a eventos y las acciones a llamadas a la API.
  Cada acción ya dice qué método usa (`actions.py`, campo `api`).
- **Memoria que sobreviva a un reinicio**: pasar `state.py` a SQLite.
- **Un temporizador** que mande `Tick` cada pocos segundos, para que venzan
  las verificaciones.

Para probarlo en un grupo de verdad hace falta una segunda cuenta de
Telegram: el bot no modera al dueño ni a los admins.
