# Mini-Torrent con tracker: un mismo script que puede ser tracker, semilla o descargador.
# El tracker hace de "directorio": las semillas se anuncian y el descargador pregunta.

import socket
import sys
import hashlib

TAM_BLOQUE = 64   # tamaño de cada trozo del archivo (64 bytes, chiquito para la demo)


def partir(ruta):
    # Lee el archivo entero y lo corta en bloques de TAM_BLOQUE bytes.
    with open(ruta, "rb") as f:
        datos = f.read()
    return [datos[i:i + TAM_BLOQUE] for i in range(0, len(datos), TAM_BLOQUE)]


def cid(bloque):
    # "Huella" del bloque: hash SHA-1 recortado a 8 caracteres.
    # Sirve para verificar que el bloque llegó sin corromperse.
    return hashlib.sha1(bloque).hexdigest()[:8]


def recibir_todo(conexion):
    # Va leyendo del socket de a 4096 bytes hasta que el otro lado cierra.
    datos = b""
    while True:
        parte = conexion.recv(4096)
        if not parte:   # recv devuelve vacío cuando cierran la conexión
            break
        datos += parte
    return datos


def pedir(peer, mensaje):
    # Mini "cliente": se conecta a un peer ("ip:puerto"), le manda un mensaje
    # de texto y devuelve todo lo que responda. Una conexión por pedido.
    ip, puerto = peer.split(":")
    s = socket.socket()
    s.connect((ip, int(puerto)))
    s.sendall(mensaje.encode())
    datos = recibir_todo(s)
    s.close()
    return datos


# El primer argumento decide qué rol juega este proceso.
rol = sys.argv[1]

if rol == "tracker":
    # ---------- TRACKER: el "directorio" central ----------
    puerto = int(sys.argv[2])
    registro = set()          # conjunto de "ip:puerto" de las semillas conocidas

    # Socket servidor clásico: bind + listen y a esperar conexiones.
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # para poder reiniciar sin esperar
    s.bind(("0.0.0.0", puerto))   # 0.0.0.0 = escucha en todas las interfaces (sirve para la red WiFi)
    s.listen()
    print(f"Tracker (DHT de juguete) activo en el puerto {puerto}.")

    while True:
        conexion, direccion = s.accept()   # direccion = (ip, puerto) de quien se conectó
        pedido = conexion.recv(1024).decode()

        if pedido.startswith("ANNOUNCE "):
            # Una semilla avisa que existe. El mensaje trae su puerto de escucha
            # (la IP no hace falta que la diga: la vemos en la conexión misma).
            puerto_semilla = pedido.split()[1]

            # TODO 1: guarda la semilla en el registro como "ip:puerto".
            registro.add(f"{direccion[0]}:{puerto_semilla}")

            conexion.sendall(b"OK")
            print(f"  + semilla registrada: {direccion[0]}:{puerto_semilla}   (total: {len(registro)})")

        elif pedido == "PEERS":
            # Un descargador pregunta quién tiene el archivo:
            # TODO 2: responde con la lista de semillas separadas por espacio.
            conexion.sendall(" ".join(registro).encode())

        conexion.close()

elif rol == "seeder":
    # ---------- SEMILLA: tiene el archivo y reparte los bloques ----------
    puerto = int(sys.argv[2])
    archivo = sys.argv[3]
    tracker = sys.argv[4]        # "ip:puerto" del tracker
    bloques = partir(archivo)    # cargo el archivo ya partido en bloques

    # TODO 3: anúnciate al tracker diciéndole tu puerto.
    pedir(tracker, f"ANNOUNCE {puerto}")

    print(f"Me anuncié al tracker {tracker}.")

    # Ahora me pongo en modo servidor para atender a los descargadores.
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", puerto))
    s.listen()
    print(f"Semilla activa en el puerto {puerto}: tengo {len(bloques)} bloques de '{archivo}'.")

    while True:
        conexion, _ = s.accept()
        pedido = conexion.recv(1024).decode()

        if pedido == "INFO":
            # Mando el "manifiesto": cuántos bloques hay y el hash de cada uno.
            # Con esto el descargador sabe qué pedir y cómo verificarlo.
            manifiesto = str(len(bloques)) + " " + " ".join(cid(b) for b in bloques)
            conexion.sendall(manifiesto.encode())

        elif pedido.startswith("GET "):
            # Me piden un bloque concreto por su número: "GET 3" -> mando el bloque 3.
            i = int(pedido.split()[1])
            conexion.sendall(bloques[i])
            print(f"  -> entregué el bloque {i} (cid {cid(bloques[i])})")

        conexion.close()

elif rol == "descargar":
    # ---------- DESCARGADOR: no tiene el archivo y no conoce a nadie ----------
    salida = sys.argv[2]
    tracker = sys.argv[3]        # "ip:puerto" del tracker (¡lo único que conocemos!)

    # TODO 4: pregúntale al tracker quién tiene el archivo.
    respuesta = pedir(tracker, "PEERS").decode().strip()

    # La respuesta es algo como "127.0.0.1:6001 127.0.0.1:6002"
    peers = respuesta.split() if respuesta else []
    if not peers:
        print("El tracker no conoce ninguna semilla. Levanta los seeders primero.")
        sys.exit(1)
    print(f"El tracker me dio {len(peers)} semilla(s): {peers}\n")

    # Le pido el manifiesto a la primera semilla: nº de bloques + hashes esperados.
    info = pedir(peers[0], "INFO").decode().split()
    n = int(info[0])
    hashes = info[1:]
    print(f"El archivo tiene {n} bloques. Descargando...\n")

    bloques = []
    for i in range(n):
        #se reparten los pedidos entre las semillas turnándolas (round-robin):
        # bloque 0 a la semilla 0, bloque 1 a la semilla 1, bloque 2 a la 0...
        peer = peers[i % len(peers)]
        bloque = pedir(peer, f"GET {i}")
        # Verifico integridad: el hash de lo que llegó debe coincidir con el del manifiesto.
        ok = (cid(bloque) == hashes[i])
        estado = "OK" if ok else "CORRUPTO!"
        print(f"bloque {i}  <-  {peer}   cid {cid(bloque)}   [{estado}]")
        if not ok:
            print("\n¡Falló la verificación de integridad! Abortando.")
            sys.exit(1)
        bloques.append(bloque)

    # Junto todos los bloques en orden y reconstruyo el archivo completo.
    with open(salida, "wb") as f:
        f.write(b"".join(bloques))
    print(f"\nArchivo reconstruido: '{salida}'")
    print("El descargador encontró las semillas vía el tracker y verificó cada bloque por su hash.")

else:
    print("Rol no válido. Usa 'tracker', 'seeder' o 'descargar'.")
