# Entregable — Mini-Torrent P2P con Tracker (Grupo 1)

**Estudiante:** Andrea Campaña

## 1. Código completado

1. **Tracker registra la semilla** cuando recibe `ANNOUNCE`:
   `registro.add(f"{direccion[0]}:{puerto_semilla}")`
2. **Tracker responde la lista** cuando recibe `PEERS`:
   `conexion.sendall(" ".join(registro).encode())`
3. **La semilla se anuncia** al tracker al arrancar:
   `pedir(tracker, f"ANNOUNCE {puerto}")`
4. **El descargador pregunta** al tracker quién tiene el archivo:
   `respuesta = pedir(tracker, "PEERS").decode().strip()`

## 2. Cómo lo probé

Abrí 4 terminales en la carpeta del proyecto y ejecuté:

```
# Terminal 1 — tracker
python mini_torrent_tracker_base.py tracker 7000

# Terminal 2 — semilla 1
python mini_torrent_tracker_base.py seeder 6001 cancion.txt 127.0.0.1:7000

# Terminal 3 — semilla 2
python mini_torrent_tracker_base.py seeder 6002 cancion.txt 127.0.0.1:7000

# Terminal 4 — descarga (solo se le pasa el tracker)
python mini_torrent_tracker_base.py descargar descargado.txt 127.0.0.1:7000
```

Resultado: el tracker registró las 2 semillas, el descargador recibió la lista
del tracker, bajó los 8 bloques alternando entre las dos semillas (todos con
hash OK) y reconstruyó `descargado.txt`, idéntico a `cancion.txt`.

## 3. Capturas

![Tracker registrando las semillas](capturas/tracker.png)

![Descargador recibiendo la lista y descargando](capturas/descarga.png)

## 4. Respuestas

### 1. ¿Qué pasa si el tracker se cae? ¿Por qué una DHT real (Chord/Kademlia) no tiene ese problema?

Si el tracker se cae, nadie puede descubrir semillas: las semillas no tienen
dónde anunciarse y el descargador no obtiene la lista, aunque las semillas
sigan vivas con el archivo. Es un **punto único de fallo**.

Una DHT real no lo tiene porque el directorio **se reparte entre todos los
nodos**: cada nodo guarda una parte de las claves y cada registro se replica
en varios nodos cercanos. Si un nodo cae, sus datos siguen en las réplicas y
las búsquedas llegan por rutas alternativas — no hay ningún nodo cuya caída
tumbe el descubrimiento.

### 2. ¿En qué se parece nuestro ANNOUNCE/PEERS a los provider records de IPFS?

Es la misma idea: un mapeo de "recurso → quién lo tiene". Nuestro `ANNOUNCE`
equivale a publicar un provider record (`CID → peer`) en IPFS, y nuestro
`PEERS` equivale a buscar el CID en la DHT para obtener los providers. La
diferencia es que en IPFS ese directorio no vive en un servidor central sino
repartido y replicado entre los nodos de Kademlia.

### 3. ¿Por qué el descargador ya no necesita conocer las direcciones de antemano?

Porque el descubrimiento ahora es **dinámico**: al descargador solo se le pasa
la dirección del tracker, y en tiempo de ejecución le pregunta con `PEERS`
quién tiene el archivo. Cualquier semilla nueva que se anuncie aparece
automáticamente en la lista, sin reconfigurar nada. Antes las direcciones eran
un dato fijo que había que pasar a mano; ahora se resuelven solas.
